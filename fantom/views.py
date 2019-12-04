import os
from wsgiref.util import FileWrapper

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseNotFound
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_text
from django.core.mail import EmailMessage
from django.contrib.auth.decorators import login_required
from django.forms.models import model_to_dict
from django.utils import timezone
from math import ceil

from .tokens import account_activation_token
from .models import Account, FBPage, VideoSeries, RawVideo, CustomizedVideo, TasksRender, Subscription
from .forms import SignupForm, LoginForm, UserSettingsForm, ManageCampaignForm, UploadVideoForm
from django.db.models.signals import post_save
from django.dispatch import receiver

from shutil import copyfile
import ffmpeg
import datetime
import requests
import json
from PIL import Image
from enum import Enum
import logging

logger = logging.getLogger("test")

QUIET_FFMPEG = True


@receiver(post_save, sender=RawVideo)
def my_handler(sender, instance, created, **kwargs):
    if created:
        if RawVideo.objects.filter(pk=instance.id).exists():
            rawvideo = RawVideo.objects.get(pk=instance.id)
            video_series = rawvideo.series
            subscribers = Subscription.objects.filter(series=video_series)
            for subscriber in subscribers:
                notify_user_series_video_uploaded(subscriber.user, rawvideo.id, rawvideo.title, video_series.name)


class Status(Enum):
    SUCCESS = 1
    FAIL = 2


def goToDashboard(user):
    if user.is_superuser:
        return redirect('users')
    else:
        return redirect('account_settings')


@login_required
def upload_video(request):
    # Only Admin account should see this
    if not request.user.is_staff:
        raise PermissionDenied

    if request.method == 'POST':
        form = UploadVideoForm(request.POST, request.FILES)
        if form.is_valid():
            required_files = ['video', 'first_insert_img', 'second_insert_img', 'first_insert_audio',
                              'second_insert_audio', 'logo']
            required_post = ['first_insert_time', 'output_width', 'output_height', 'logo_placement']
            # store the uploaded assets in a temp folder, and then we also delete these files
            fs = FileSystemStorage(location=settings.TEMP_ROOT)
            # render video and upload it

            params = {}
            for rp in required_post:
                if rp in form.data:
                    params[rp] = form.data[rp]

            saved_files = {}
            files_to_delete = []
            for t in required_files:
                if t in request.FILES:
                    myfile = request.FILES[t]
                    filename = fs.save(myfile.name, myfile)
                    files_to_delete.append(filename)
                    saved_files[t] = os.path.join(settings.TEMP_ROOT, filename)

            rendered_video_url, _ = render_video2(request, saved_files,
                                                  params)  # TODO:: remove saved_files after this call returns?

            if rendered_video_url:
                # if Account.objects.filter(pk=request.user.id).exists():
                #     user = Account.objects.get(pk=request.user.id)
                #     user.credit +=1
                #     user.save()
                messages.info(request, "Video was uploaded successfully")
                for fn in files_to_delete:
                    fs.delete(fn)
            return render(request, 'upload_video.html', {'form': form, 'rendered_video': rendered_video_url})
    else:
        form = UploadVideoForm()
    return render(request, 'upload_video.html', {'form': form})


def timestamp2frames(ts, fps_v):
    """

    Args:
        ts: expects a string which is a suffix of "hours:minutes:seconds:frames"
        fps_v:

    Returns:

    """
    times = [int(t) for t in ts.split(":")]
    insert_in_seconds = times[-1] / fps_v
    scale = 1
    # add seconds + minutes_in_seconds + hours_in_seconds
    for t in range(len(times) - 2, -1, -1):
        insert_in_seconds += (times[t] * scale)
        scale *= 60
    return insert_in_seconds


def scale_insert_video(vid, resolution, outname):
    (insert_length, insert_width, insert_height, insert_fps_v, insert_fps_s, insert_codec) = probe_video(vid)
    return trim_and_scale(vid, 0, insert_length, resolution, outname)


def render_video_with_inserts(rawvideo, insert1, insert2, logo_path, resolution, logo_placement="bottom_left"):
    # rawvideo is models.RawVideo instance
    # inserts can be tuple of File objects - in which case it's image + audio - or single, in which case it's a video file
    # logo_path is path to a logo file, or None
    # returns file object, error

    logger.debug("[render_video_with_inserts] begin rendering the inserts on the video %s" % (rawvideo))
    basename = "composite_video"
    # composites_folder = "rendered"
    timestamp_suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    composite_name = "_".join([basename, timestamp_suffix]) + ".mp4"

    out_name = os.path.join(settings.MEDIA_ROOT, composite_name)
    workdir = os.path.join(settings.MEDIA_ROOT, 'work_area')

    os.makedirs(workdir, exist_ok=True)

    VIDEO_PARTS_TEMPLATE_NAMES = [
        "part1.%s.mp4" % timestamp_suffix,
        "part2.%s.mp4" % timestamp_suffix,
        "insert1.%s.mp4" % timestamp_suffix,
        "insert2.%s.mp4" % timestamp_suffix,
    ]

    WORK_FILES_TO_DELETE = [os.path.join(workdir, VIDEO_PARTS_TEMPLATE_NAMES[0])]

    # input files names and params
    inputfilename = rawvideo.video.path

    out_width, out_height = resolution

    # probe input video
    (length, width, height, fps_v, fps_s, codec) = probe_video(inputfilename)
    insert_time_1 = "00:00:12:00"
    if bool(rawvideo.insert_time_1):
        insert_time_1 = rawvideo.insert_time_1
    insert_time_in_seconds = timestamp2frames(insert_time_1, fps_v)
    print("insert_time is %.4f secs" % insert_time_in_seconds)
    logger.debug("[render_video_with_inserts] insert_time is %.4f secs" % (insert_time_in_seconds))

    logger.debug("[render_video_with_inserts] Part 1 begin")
    # PART 1: load video file and scale it. change display-aspect-ratio of the output so it's consistent, for all the files.
    WORK_FILES_TO_DELETE.append(os.path.join(workdir, VIDEO_PARTS_TEMPLATE_NAMES[1]))

    status, msg = trim_and_scale(inputfilename, 0, insert_time_in_seconds, resolution, WORK_FILES_TO_DELETE[0],
                                 logo_placement, logo_path)
    if status == Status.FAIL:
        return status, msg

    status, msg = trim_and_scale(inputfilename, insert_time_in_seconds, length - insert_time_in_seconds, resolution,
                                 WORK_FILES_TO_DELETE[1], logo_placement, logo_path)
    if status == Status.FAIL:
        return status, msg

    resized_insert1_path = os.path.join(workdir, VIDEO_PARTS_TEMPLATE_NAMES[2])
    WORK_FILES_TO_DELETE.append(resized_insert1_path)
    if len(insert1) == 2:
        # create slides with audio for inserts. set frame rate, display-aspect-ratio
        first_insert = create_slide(insert1[0], insert1[1], out_width, out_height, resized_insert1_path, fps_v)

    else:
        # first insert is a video - we don't need to concatenate audio
        status, msg = scale_insert_video(insert1[0], resolution, resized_insert1_path)
        if status == Status.FAIL:
            return status, msg

    logger.debug("[render_video_with_inserts] Part 2 begin")
    # PART 2: concatenate all parts together and write output video
    part1 = ffmpeg.input(WORK_FILES_TO_DELETE[0])
    ### add part 1 of the original video
    streams = [part1['v'], part1['a']]
    ### add first insert to ffmpeg command
    insert = ffmpeg.input(resized_insert1_path)
    streams += [insert['v'], insert['a']]
    ### add part 2 of the original video
    part2 = ffmpeg.input(WORK_FILES_TO_DELETE[1])
    streams += [part2['v'], part2['a']]

    logger.debug("[render_video_with_inserts] Part 3 begin")
    # PART 3: convert second insert to video and add it to list of streams
    if len(insert2) > 0:
        resized_insert2_path = os.path.join(workdir, VIDEO_PARTS_TEMPLATE_NAMES[3])
        WORK_FILES_TO_DELETE.append(resized_insert2_path)

        if len(insert2) == 2:
            second_insert = create_slide(insert2[0], insert2[1], out_width, out_height,
                                         resized_insert2_path, fps_v)
        else:
            status, msg = scale_insert_video(insert2[0], resolution, resized_insert2_path)
            if status == Status.FAIL:
                return status, msg

        insert = ffmpeg.input(resized_insert2_path)
        streams += [insert['v'], insert['a']]

    else:
        pass  # no second insert

    logger.debug("[render_video_with_inserts] calling ffmpeg to concatenate streams")
    # give all streams to ffmpeg
    print('calling ffmpeg to concatenate streams')
    ffmpeg.concat(*streams, v=1, a=1).output(out_name).overwrite_output().run(quiet=QUIET_FFMPEG)

    # in debug mode, keep files. otherwise, delete all temp files
    if (settings.DEBUG == False):
        for name in WORK_FILES_TO_DELETE:
            os.remove(name)

    fs = FileSystemStorage()
    logger.debug("[render_video_with_inserts] end")
    return fs.url(composite_name), out_name


####
####
####
####
####
####
####
####
####
####
####
####   OLD CODE BELOW   #########

def render_video2(request, files, params):
    basename = "composite_video"
    suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    composite_name = "_".join([basename, suffix]) + ".mp4"
    out_name = os.path.join(settings.MEDIA_ROOT, composite_name)
    workdir = os.path.join(settings.MEDIA_ROOT, 'work_area')
    os.makedirs(workdir, exist_ok=True)

    output_file_names_ = [
        "part1.%s.mp4" % suffix,
        "part2.%s.mp4" % suffix,
        "insert1.%s.mp4" % suffix,
        "insert2.%s.mp4" % suffix,
    ]
    outnames = [os.path.join(workdir, output_file_names_[0])]

    # input files names and params
    inputfilename = files['video']
    logo_name = None
    if 'logo' in files:
        logo_name = files['logo']
    out_width = int(params['output_width'])
    out_height = int(params['output_height'])
    resolution = (out_width, out_height)
    logo_placement = params['logo_placement']

    # probe input video
    (length, width, height, fps_v, fps_s, codec) = probe_video(inputfilename)
    # PART 1: load video file and scale it. If first insert exist, split video and convert first insert to video
    onames1 = []
    if 'first_insert_time' in params and params['first_insert_time'] != '':
        insert_in_seconds = timestamp2frames(params['first_insert_time'], fps_v)
        # scale input video. change display-aspect-ratio of the output so it's consistent, for all the files.
        outnames.append(os.path.join(workdir, output_file_names_[1]))
        status1, msg1 = trim_and_scale(inputfilename, 0, insert_in_seconds, resolution, outnames[0], logo_placement,
                                       logo_name)
        if status1 == Status.FAIL:
            messages.error(request, msg1)
            return None
        status2, msg2 = trim_and_scale(inputfilename, insert_in_seconds, length - insert_in_seconds, resolution,
                                       outnames[1], logo_placement, logo_name)
        if status2 == Status.FAIL:
            messages.error(request, msg2)
            return None

        if 'first_insert_img' in files and 'first_insert_audio' in files and files['first_insert_audio'] != '':
            # create slides with audio for inserts. set frame rate, display-aspect-ratio
            outnames.append(os.path.join(workdir, output_file_names_[2]))
            onames1 = create_slide(files['first_insert_img'], files['first_insert_audio'], out_width, out_height,
                                   outnames[-1], fps_v)
        elif 'first_insert_img' in files and files['first_insert_img'].lower().endswith(".mp4"):
            outnames.append(os.path.join(workdir, output_file_names_[2]))
            # first insert is a video - we don't need to concatenate audio
            status, msg = scale_insert_video(files['first_insert_img'], resolution, outnames[-1])
            if status == Status.FAIL:
                messages.error(request, msg)
                return None
            onames1 = [outnames[-1]]

    else:
        # no first insert - don't need to split video
        status, msg = trim_and_scale(inputfilename, 0, length, resolution, outnames[0], logo_placement, logo_name)
        if status == Status.FAIL:
            messages.error(request, msg)
            return None

    # PART 2: concatenate all parts together and write output video
    part1 = ffmpeg.input(outnames[0])
    # add part 1 of the original video
    streams = [part1['v'], part1['a']]

    if len(outnames) > 1:
        # add all parts of the first insert
        for name in onames1:
            insert = ffmpeg.input(name)
            streams += [insert['v'], insert['a']]
        # add part 2 of the original video
        part2 = ffmpeg.input(outnames[1])
        streams += [part2['v'], part2['a']]

    onames2 = []
    # PART 3: convert second insert to video and add it to list of streams
    if 'second_insert_img' in files and 'second_insert_audio' in files and files['second_insert_audio'] != '':
        outnames.append(os.path.join(workdir, output_file_names_[3]))
        onames2 = create_slide(files['second_insert_img'], files['second_insert_audio'], out_width, out_height,
                               outnames[-1],
                               fps_v)
    elif 'second_insert_img' in files and files['second_insert_img'].lower().endswith(".mp4"):
        outnames.append(os.path.join(workdir, output_file_names_[3]))
        # first insert is a video - we don't need to concatenate audio
        status, msg = scale_insert_video(files['second_insert_img'], resolution, outnames[-1])
        if status == Status.FAIL:
            messages.error(request, msg)
            return None
        onames2 = [outnames[-1]]
    # add all parts of the second insert
    for name in onames2:
        insert = ffmpeg.input(name)
        streams += [insert['v'], insert['a']]

    # concat all streams
    print('concatenating streams')
    ffmpeg.concat(*streams, v=1, a=1).output(out_name).overwrite_output().run(quiet=QUIET_FFMPEG)

    # in debug mode, keep files. otherwise, delete all temp files
    if (settings.DEBUG == False):
        for name in outnames:
            os.remove(name)

    fs = FileSystemStorage()
    return fs.url(composite_name), out_name


def create_slide(imagefile, audiofile, width, height, outputts, rate):
    # probe input audio
    probe = ffmpeg.probe(audiofile)
    audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
    length = float(audio_stream['duration'])

    baseimagefile, extimagefile = os.path.splitext(imagefile)

    for i in range(2):
        copyfile(imagefile, "%s_%d%s" % (baseimagefile, i, extimagefile))

    # each slide is half second video made of two images
    slide = ffmpeg.input("%s_%s%s" % (baseimagefile, "%d", extimagefile), r=4)

    n = ceil(length * 2)  # We will need that many "slides" of half second each

    slidenames = [slide for i in range(n)]
    slides = ffmpeg.concat(*slidenames).filter('scale', width, height).filter('setdar', '16/9')

    # combine all slides with audio, and save
    audio = ffmpeg.input(audiofile)
    ffmpeg.output(slides, audio, outputts, r=4).overwrite_output().run(quiet=QUIET_FFMPEG)
    return [outputts]


def probe_video(fname):
    print("probing " + fname)
    logger.debug("prob step 1 %s" % fname)
    probe = ffmpeg.probe(fname)
    logger.debug("prob step 2")
    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    logger.debug("prob step 3")
    width = int(video_stream['width'])
    logger.debug("prob step 4")
    height = int(video_stream['height'])
    logger.debug("prob step 5")
    length = float(video_stream['duration'])
    logger.debug("prob step 6")
    fps = video_stream['r_frame_rate']
    logger.debug("prob step 7")
    codec = video_stream['codec_name']

    try:
        fps_v = float("%3.2f" % eval(fps))
    except:
        fps_v = None
    logger.debug("prob step 8")

    return (length, width, height, fps_v, fps, codec)


LOGO_OFFSET = 15
MAX_LOGO = [296, 150]


def calc_resize(box, container):
    # given a bbox box, how would it scale to fit inside bbox container?
    # examples:
    # (50,100) and (200,200) ==> ratio = 2      new box is (100,200)
    # (50,100) and (10,25)   ==> ratio = 0.2    new box is (10,20)
    # (100,100) and (150,296)==> ratio = 1.5    new box is (150,150)

    (a, b) = box
    (X, Y) = container
    ratio1 = X / a
    ratio2 = Y / b
    ratio = min(ratio1, ratio2)
    newbox = (ratio * a, ratio * b)
    return newbox


def calc_image_resize(imagefile, container):
    im = Image.open(imagefile)
    return calc_resize(im.size, container)


def trim_and_scale(inputfilename, start_time, length, resolution, outname, logo_placement="bottom_left",
                   overlay_image=None):
    (width, height) = resolution

    print("trim_and_scale [%.4f secs] of %s => %s at resolution %s" % (length, inputfilename, outname, resolution))
    input = ffmpeg.input(inputfilename, ss=start_time, t=length)
    in_v = input['v']
    in_a = input['a']
    in_v = in_v.filter('scale', width, height).filter('setdar', '16/9')
    if overlay_image:
        new_logo_size = calc_image_resize(overlay_image, MAX_LOGO)

        overlay = ffmpeg.input(overlay_image).filter('scale', new_logo_size[0], new_logo_size[1])

        if logo_placement == "bottom_left":
            in_v = in_v.overlay(overlay, y=height - new_logo_size[1] - LOGO_OFFSET, x=LOGO_OFFSET)
        elif logo_placement == "top_left":
            in_v = in_v.overlay(overlay, y=LOGO_OFFSET, x=LOGO_OFFSET)
        elif logo_placement == "top_right":
            in_v = in_v.overlay(overlay, y=LOGO_OFFSET, x=width - new_logo_size[0] - LOGO_OFFSET)
        elif logo_placement == "bottom_right":
            in_v = in_v.overlay(overlay, y=height - new_logo_size[1] - LOGO_OFFSET,
                                x=width - new_logo_size[0] - LOGO_OFFSET)

    try:
        ffmpeg.output(in_v, in_a, outname).overwrite_output().run(quiet=QUIET_FFMPEG)
    except Exception as e:
        print(e)
        return Status.FAIL, "Couldn't scale video - %s, you must provide valid video with audio" % inputfilename
    return Status.SUCCESS, ""


def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            mail_subject = 'Activate your test account.'
            message = render_to_string('acc_active_email.html', {
                'user': user,
                'domain': settings.DEFAULT_DOMAIN,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)).decode(),
                'token': account_activation_token.make_token(user),
            })
            to_email = form.cleaned_data.get('email')
            email = EmailMessage(
                mail_subject, message, to=[to_email]
            )
            email.send()
            messages.info(request,
                          "Please confirm your email address to complete the registration. Check your spam folder if you can't see the confirmation email.")
            return redirect('home')
    else:
        form = SignupForm()
    return render(request, 'signup.html', {'form': form})


def activate(request, uidb64, token):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = None
        if Account.objects.filter(pk=uid).exists():
            user = Account.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError):
        user = None
    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.info(request, 'Account is activated successfully!')
        return goToDashboard(user)
    else:
        return HttpResponse('Activation link is invalid!')


def user_login(request):
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = LoginForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try:
                # Use Django's machinery to attempt to get account from email
                account = Account.objects.get(email=email)
            except Account.DoesNotExist:
                account = None

            # check if we can authenticate the account/password combination.
            # if it is valid we get a User object, and login the user if she's active
            if account:
                user = authenticate(username=account.username, password=password)
                if user:
                    # Is the account active? It could have been disabled.
                    if user.is_active:
                        # If the account is valid and active, we can log the user in.
                        # We'll send the user to dashboard - account settings page
                        login(request, user)
                        if len(request.GET) < 1:
                            return goToDashboard(user)
                        else:
                            return redirect(request.GET['next'])
                    else:
                        # An inactive account was used - no logging in!
                        return HttpResponseForbidden("Your account is disabled")

            # this case should not happen because user is already authenticated inside the form's clean() method.
            # Bad login details were provided. So we can't log the user in.
            messages.error(request, "This email and password combination is invalid, please try again")
            return render(request, 'home.html', {'form': form})

    # if a GET (or any other method) we'll create a blank form
    else:
        form = LoginForm()

    return render(request, 'home.html', {'form': form})


@login_required
def user_settings(request):
    user = request.user
    app_server_protocol = "http://" if settings.DEFAULT_DOMAIN.find("localhost") >= 0 else "https://"
    app_server = "%s%s" % (app_server_protocol, settings.DEFAULT_DOMAIN)

    if request.method == 'POST':
        form = UserSettingsForm(request.POST, request.FILES)
        if form.is_valid():
            # update user account
            user.business_name = form.data['business_name']
            user.address1 = form.data['address1']
            user.address2 = form.data['address2']
            user.zip_code = form.data['zip_code']
            user.state = form.data['state']
            user.city = form.data['city']
            # user.country = form.data['country']
            user.description = form.data['description']
            user.coupon_description = form.data['coupon_description']
            file_fields = ['dark_brand_logo', 'light_brand_logo', 'first_insert', 'first_insert_audio', 'second_insert', 'second_insert_audio']
            for name in file_fields:
                if form.cleaned_data[name]:
                    setattr(user, name, form.cleaned_data[name])
            user.save()
            messages.info(request, "Account was updated successfully")
            return goToDashboard(user)
        else:
            messages.error(request, 'Something in this form was wrong: %s' % form.errors[0])
    else:
        form = UserSettingsForm(initial=model_to_dict(user))

    pages = list_pages_for_facebook_user(request.user)
    if len(pages) > 0:
        fb_connected = 1
        fb_pageID = pages[0]['fb_pageID']
        fb_pageName = pages[0]['fb_pageName']
    else:
        fb_connected = 0
        fb_pageID = '--'
        fb_pageName = '--'

    return render(request, 'account_settings.html', {'form': form,
                                                     'fb_connected': fb_connected,
                                                     'fb_pageID': fb_pageID,
                                                     'fb_pageName': fb_pageName,
                                                     'FB_APP_ID': settings.FB_APP_ID,
                                                     'APP_SERVER': app_server})


@login_required
def distribute(request):
    return render(request, 'distribute.html')


@login_required
def users(request):
    # Only admin account can see this page
    if not request.user.is_staff:
        raise PermissionDenied

    accounts = Account.objects.all()
    return render(request, 'users.html', {'accounts': accounts})


def user_logout(request):
    # log the user out.
    logout(request)

    # Take the user back to the homepage.
    return redirect('home')


@login_required
def dashboard(request):
    return goToDashboard(request.user)


@login_required
def facebook_pages_for_user(request):
    if request.method == 'GET':
        response = JsonResponse({'data': list_pages_for_facebook_user(request.user)})
        response["Access-Control-Allow-Origin"] = "test.com"
        return response

    elif request.method == 'POST':
        print('facebook_user_1 got post ')
        required = ['fbid', 'fbtoken']
        for t in required:
            if t not in request.POST:
                return HttpResponse("error - missing %s" % t)

        fbid = request.POST['fbid']
        fbtoken = request.POST['fbtoken']

        result = fb_list_accounts(uid=fbid,
                                  uidaccesstoken=fbtoken)
        if result is None:
            return JsonResponse({'status': 'error', 'error': "could not find any facebook pages to post to"})

        current_time = timezone.make_aware(datetime.datetime.now(), timezone.get_current_timezone())

        (pagename, pageid, pageaccesstoken, token_expiration) = result

        token_expiration = current_time + datetime.timedelta(seconds=token_expiration)
        FBPage.objects.create(owner=request.user,
                              fb_userID=fbid,
                              fb_pageID=pageid,
                              fb_pageName=pagename,
                              fb_pageAccessToken=pageaccesstoken,  # TODO: replace with permanent access token
                              added_timestamp=current_time,
                              token_expiration=token_expiration)
        return JsonResponse({'status': 'ok', 'data': {'fb_pageID': pageid, 'fb_pageName': pagename}})

    else:
        return HttpResponseForbidden('GET or POST only')


@login_required
def delete_facebook(request):
    user = request.user
    username = user.username

    if request.method == 'POST':
        fbpages = FBPage.objects.filter(owner=user)
        if len(fbpages) == 0:
            return JsonResponse({'status': 'error', 'error': 'no pages found for user %s' % username})
        fbpage = fbpages[0]
        fb_userID = fbpage.fb_userID

        fburl = 'https://graph.facebook.com/v3.2/%s/permissions' % fb_userID
        app_ids_as_access_token = '%s|%s' % (settings.FB_APP_ID, settings.FB_APP_SECRET)
        r = requests.delete(fburl, data={'access_token': app_ids_as_access_token})
        s = r.content.decode('utf-8')
        if r.status_code != 200:
            return JsonResponse({'status': 'error', 'error': 'facebook responded with an error, %s' % s[:200]})
        js = json.loads(s)
        if 'success' in js and js['success'] == True:
            fbpage.delete()
            return JsonResponse({'status': 'ok'})
        else:
            return JsonResponse({'status': 'error', 'error': 'facebook responded with "%s"' % s[:200]})
    else:
        return HttpResponseForbidden('POST is required')


def list_pages_for_facebook_user(user):
    qs = FBPage.objects.filter(owner=user)
    return [q.json() for q in qs]


def fb_list_accounts(uid, uidaccesstoken):
    fburl = 'https://graph.facebook.com/v3.2/%s/accounts?access_token=%s' % (uid, uidaccesstoken)
    print(fburl)
    r = requests.get(fburl)
    if r.status_code != 200:
        print("fb_list_accounts error for uid %s" % uid, r.status_code)
        return None

    s = r.content.decode('utf-8')
    js = json.loads(s)
    if 'data' not in js:
        print("fb_list_accounts error - can't find any data in response for fb_uid %s" % uid, js)
        return None

    mydata = js['data']
    if len(mydata) > 0:
        page = mydata[0]
        pagename, pageid, pageaccesstoken = page['name'], page['id'], page['access_token']
        token_expiration = 60 * 60 * 1000  # one hour

        extended_page_token = extend_page_token(pageaccesstoken, uid)
        if extended_page_token is not None:
            pageaccesstoken = extended_page_token["access_token"]
            token_expiration = extended_page_token["expires_in"]

        return (pagename, pageid, pageaccesstoken, token_expiration)
    else:
        print("fb_list_accounts error - response has data but no pages, for fb_uid %s" % uid, js)
        return None


def extend_page_token(short_term_token, uid):
    fburl = "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s" % (
        settings.FB_APP_ID,
        settings.FB_APP_SECRET,
        short_term_token
    )

    r = requests.post(fburl)
    if r.status_code != 200:
        print("extend_page_token error for uid %s" % uid, r.status_code)
        return None

    s = r.content.decode('utf-8')
    js = json.loads(s)
    return js


def postVideo(user, video_url, text):
    qs = FBPage.objects.filter(owner=user)
    if len(qs) == 0:
        return False
    page = qs[0]

    fburl = 'https://graph-video.facebook.com/v3.2/%s/videos' % page.fb_pageID

    datadict = {
        'access_token': page.fb_pageAccessToken,
        'description': text,
        'title': "sport video of the day",
        'file_url': video_url,
    }

    r = requests.post(fburl, data=datadict)
    print("submitted, status_code =", r.status_code, r.content)
    if r.status_code == 200:
        return True
    else:
        return False


@login_required
def manage_campaign(request, userid):
    # Only admin account can see this page
    if not request.user.is_staff:
        raise PermissionDenied

    user = Account.objects.get(pk=userid)
    fb_connected = is_connected(user, 'facebook')

    if request.method == 'POST':
        form = ManageCampaignForm(request.POST)
        if form.is_valid():

            print('video url: ', form.data['video_url'])
            print('coupon url: ', form.data['coupon_url'])
            if (form.data['social_network'] == 'facebook'):
                print('Publish on facebook, calling ', 'postVideoToFacebook(getFBPage(user), video_url, coupon_url)')
                res = postVideo(user, form.data['video_url'], form.data['coupon_url'])
                if res:
                    messages.info(request, "Success! Posted on " + form.data['social_network'])
                else:
                    messages.error(request, "Failed to post to " + form.data['social_network'])
        else:
            messages.warning(request, "Missing something, please correct and try again.")
    else:
        form = ManageCampaignForm()
    return render(request, 'manage_campaign.html',
                  {'form': form, 'username': user.username, 'fb_connected': fb_connected})


def is_connected(user, network):
    if network == 'facebook':
        pages = list_pages_for_facebook_user(user)
        if len(pages) > 0:
            connected = 1
        else:
            connected = 0

        return connected
    else:
        return 0


@login_required
def view_series(request):
    if request.method != 'GET':
        return HttpResponseForbidden("Gotta Get Geet!")
    return render(request, 'series_dashboard.html', {"series": VideoSeries.objects.all()})


@login_required
def view_video(request, video_id):
    if request.method != 'GET':
        return HttpResponseForbidden("Gotta Get Geet!")
    video = get_object_or_404(RawVideo, pk=video_id)
    return render(request, 'view_video.html', {"video": video,
                                               "next_video": next_video(video),
                                               "prev_video": prev_video(video)})


def next_video(video: RawVideo):
    series = video.series
    video_date = video.date_created

    videos = RawVideo.objects.filter(
        series=series,
        date_created__gt=video_date
    ).order_by('date_created')

    if len(videos) == 0:
        return None

    return videos[0]


def prev_video(video: RawVideo):
    series = video.series
    video_date = video.date_created

    videos = RawVideo.objects.filter(
        series=series,
        date_created__lt=video_date
    ).order_by('-date_created')

    if len(videos) == 0:
        return None

    return videos[0]

@login_required
def download_video(request, video_id):
    if request.method != 'GET':
        return HttpResponseForbidden("Gotta Get Geet!")
    video = get_object_or_404(RawVideo, pk=video_id)
    user = request.user
    if not user.eligible():
        return HttpResponseForbidden("Error: user %s isn't eligible to render videos" % user)
    if not user.downloadable():
        return HttpResponseForbidden("Error: user %s is dummy so can't download videos" % user)

    video_url, composite_name = render_video_for_user(user, video)
    save_video_for_user(user, video, video_url)

    logger.debug("[download_video] saving video %s" % video_url)
    print("Done rendering video - " + composite_name)

    with open(composite_name, 'rb') as file:
        print("Packing video for download")
        file_wrapper = FileWrapper(file)
        response = HttpResponse(file_wrapper, content_type='video/mp4')
        today = datetime.date.today().strftime("%B-%d-%Y")
        filename = "%s-%s.mp4" % (user.business_name, today)
        response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    print("Responding")

    return response


def render_video_for_user(user, video):
    logger.debug("[render_video_for_user] user %s, video %s" % (user, video))
    if not user.eligible():
        logger.debug("[render_video_for_user] user %s is not eligible for video %s" % (user, video))
        raise RuntimeError("user %s not eligible for video" % user)

    if settings.DEBUG:
        resolution = (640, 360)
    else:
        resolution = (1920, 1080)

    if video.logo_type == 'dark':
        logo_path = user.dark_brand_logo.path if bool(user.dark_brand_logo) else None
    else:
        logo_path = user.light_brand_logo.path if bool(user.light_brand_logo) else None
        
    insert1 = [user.first_insert.path]
    if bool(user.first_insert_audio):
        insert1.append(user.first_insert_audio.path)

    insert2 = []
    if bool(user.second_insert):
        insert2.append(user.second_insert.path)
    if bool(user.second_insert_audio):
        insert2.append(user.second_insert_audio.path)

    logger.debug("[render_video_for_user] insert videos and logo path are ready")
    # video_url, composite_name = render_video2(request, saved_files, params)
    video_url, composite_name = render_video_with_inserts(video, insert1, insert2, logo_path, resolution,
                                                          logo_placement=video.logo_placement)

    return video_url, composite_name


def save_video_for_user(user, video, video_url):
    cvs = CustomizedVideo.objects.filter(user=user, video=video)
    if cvs.exists():
        for cv in cvs:
            cv.delete()

    cv = CustomizedVideo(user=user, video=video, url=video_url)
    cv.save()

    rt = TasksRender.objects.filter(user=user, video=video)
    if rt.exists():
        rrr = rt.first()
        rrr.delete()


def notify_user_series_video_uploaded(user,video_id,video_title,series_name):
    mail_subject = 'New Video Uploaded To Your Subscribed Series'
    message = render_to_string('video_added_notice.html', {
        'user': user,
        'domain': settings.PLATFORM_DOMAIN,
        'series_name': series_name,
        'video_id': video_id,
        'video_title': video_title,
    })
    to_email = user.email
    email = EmailMessage(
        mail_subject, message, to=[to_email]
    )
    email.content_subtype = 'html'
    email.send()


def notify_user_task_rendered(user, video, video_url):
    mail_subject = 'Your test is Loaded'
    message = render_to_string('video_rendered_notice.html', {
        'user': user,
        'domain': settings.DEFAULT_DOMAIN,
        'video_url': video_url,
    })
    to_email = user.email
    email = EmailMessage(
        mail_subject, message, to=[to_email]
    )
    email.content_subtype = 'html'
    email.send()
