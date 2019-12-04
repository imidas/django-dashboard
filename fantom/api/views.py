from django.http import JsonResponse
from django.conf import settings
from django_filters import rest_framework

from url_filter.integrations.drf import DjangoFilterBackend
from rest_framework.filters import OrderingFilter,SearchFilter
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

from fantom.models import Account, FBPage, VideoSeries, RawVideo, CustomizedVideo, TasksRender, Subscription, Cart, Campaign, DraftVideo
from fantom import views as faviews
from fantom.views import Status
from .serializers import *

from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics

import traceback
import threading
import time
import logging

logger = logging.getLogger("test")

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = Account.objects.all()
    serializer_class = UserSerializer

    def get_object(self, queryset=None):
        obj = self.request.user
        return obj

    @action(methods=['post'], detail=True, permission_classes=(IsAuthenticated,),serializer_class=PasswordSerializer,
            url_path='change-password', url_name='change_password')
    def set_password(self, request, pk=None):
        user = self.get_object()
        serializer = PasswordSerializer(data=request.data)

        if serializer.is_valid():
            if not user.check_password(serializer.data.get('old_password')):
                return Response({'old_password': ['Wrong password.']},
                                status=status.HTTP_400_BAD_REQUEST)
            # set_password also hashes the password that the user will get
            user.set_password(serializer.data.get('new_password'))
            user.save()
            return Response({'status': 'password set'}, status=status.HTTP_200_OK)

        return Response(serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(generics.UpdateAPIView):
    """
    An endpoint for changing password.
    """
    serializer_class = PasswordSerializer
    model = Account
    permission_classes = (IsAuthenticated,)

    def get_object(self, queryset=None):
        obj = self.request.user
        return obj

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Check old password
            if not self.object.check_password(serializer.data.get("old_password")):
                return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
            # set_password also hashes the password that the user will get
            self.object.set_password(serializer.data.get("a"))
            self.object.save()
            return Response("Success.", status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class FBPageViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = FBPageSerializer
    queryset = FBPage.objects.all()


class SeriesViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = SeriesSerializer
    queryset = VideoSeries.objects.all()

    #filter_backends = [DjangoFilterBackend,rest_framework.DjangoFilterBackend,OrderingFilter,SearchFilter] #,filters.SearchFilter]
    filter_backends = [DjangoFilterBackend,OrderingFilter]  #use rest_url filters which gives range filtering
    filter_fields = ("hosts", "category", "average_length","channels","min_recommended_age","max_recommended_age","gender","delivered","content_stale",)
    ordering_fields = '__all__'

    @action(detail=False, permission_classes=(permissions.IsAuthenticated,),url_path='populate')
    def request_creators(self, request, pk=None, userid=None, videoid=None):
        avg_length_list=[]
        host_values = list(VideoSeries.objects.values_list('hosts',flat=True).exclude(hosts='').distinct()) #.filter(...)
        videos = VideoSeries.objects.all()
        for video in videos:
            avg_length_list.append(str(video.average_length))
        format = list(VideoSeries.objects.values_list('channels', flat=True).exclude(channels='').distinct())  # .filter(...)
        min_recomm_age = list(VideoSeries.objects.values_list('min_recommended_age', flat=True).distinct())  # .filter(...)
        max_recomm_age = list(VideoSeries.objects.values_list('max_recommended_age', flat=True).distinct())  # .filter(...)
        return JsonResponse({'status':'success', 'hosts': host_values, 'format':format, 'average_length':avg_length_list, 'min_recommend_age': min_recomm_age, 'max_recommend_age':max_recomm_age})


class RawVideoViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = RawVideoSerializer
    queryset = RawVideo.objects.all()
    filter_backends = [OrderingFilter] #use rest framework filters instead of django-filters
    ordering = ['-date_created']
    ordering_fields = '__all__'


class TasksRenderViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = TasksRenderSerializer
    queryset = TasksRender.objects.all()
    ordering_fields = '__all__'
    filterset_fields = '__all__'


class SubscriptionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = SubscriptionSerializer
    queryset = Subscription.objects.all()
    ordering_fields = '__all__'
    filterset_fields = '__all__'


class CustomizedVideoViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = CustomizedVideoSerializer
    queryset = CustomizedVideo.objects.all()
    ordering_fields = '__all__'

    @action(methods=['get'], detail=False, permission_classes=(permissions.IsAuthenticated,),
            url_path='(?P<userid>\d+)/(?P<videoid>\d+)')
    def request_customized_video(self, request, pk=None, userid=None, videoid=None):
        logger.debug("request customized video")
        maybe_start_renderer_thread()

        try:
            user = Account.objects.get(pk=userid)
        except:
            return JsonResponse({"status": "error", "message": "user %s doesn't exist" % userid})

        if not user.downloadable():
            return JsonResponse({"status": "error", "message": "dummy user %s can't download any video" % userid})

        try:
            video = RawVideo.objects.get(pk=videoid)
        except:
            return JsonResponse({"status": "error", "message": "video %s doesn't exist" % videoid})

        try:
            cv = CustomizedVideo.objects.filter(user=user, video=video)
            if cv.exists():
                cc = cv.first()
                print("found customized video %s for user %s" % (video, user))
                if cc.downloaded is not True:
                    cc.downloaded = True
                    cc.save()
                return JsonResponse({"status": "ready", "message":("http://" + settings.DEFAULT_DOMAIN + cc.url)})

            # no customized video ready yet

            rt = TasksRender.objects.filter(user=user, video=video)
            if rt.exists():
                rrr = rt.first()
                print("Task %s to render video %s for user %s was found" % (rrr, video, user))
                return JsonResponse({"status": "pending", "message": "already existed"})
            else:
                eligible, msg = userEligibleToRenderVideo(user, video)
                # user_remaining_credit = user.credit - video.credit
                # if user_remaining_credit < 0:
                    # return JsonResponse({"status": "error","message": "user %s isn't eligible to render video %s due to insufficient credit" % (user, video)})
                # elif eligible:
                if eligible:
                    addRenderTask(user, video)
                    # user.credit -= video.credit
                    user.save()
                    return JsonResponse({"status": "pending", "message": "added now"})
                else:
                    return JsonResponse({"status": "error",
                                         "message": "user %s not eligible to render video %s: %s" % (user, video, msg)})
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({"status": "error", "message": str(e)})


def userEligibleToRenderVideo(user, video):
    if user.eligible():
        return True, "user has assets OK"
    else:
        return False, "no assets for rendering found"


def addRenderTask(user, video):
    task = TasksRender(user=user, video=video)
    task.save()
    print("adding task to render video %s for user %s" % (video, user))


def maybe_start_renderer_thread():
    logger.debug("check if Renderer Thread is running")
    if settings.RENDERER_THREAD is not None:
        return

    logger.debug("Starting a rendered thread")
    print("Starting a rendered thread")
    settings.RENDERER_THREAD = threading.Thread(target=do_rendering_tasks, name="rendering videos")
    settings.RENDERER_THREAD.setDaemon(True)
    settings.RENDERER_THREAD.start()


def do_rendering_tasks():
    while True:
        tasks = TasksRender.objects.all().order_by('-priority', 'date_requested')
        if tasks.exists():
            task = tasks.first()
            try:
                user = task.user
                video = task.video
            except:
                if task.priority < 0:
                    print("error while reading rendering task, deleting this task %s" % task)
                    task.delete()
                else:
                    print("error while reading rendering task %s" % task)
                    task.priority = task.priority - 5
                    task.save()
                continue

            if not user.eligible():
                task.priority = 0
                task.save()
                print("WARNING: task %s to render for user %s (%s) - user is ineligible.")
                continue
            else:
                print("Doing task %s with priority %d: render video %s for user %s (%s)" % (
                    task.id, task.priority, video, user.id, user))

                logger.debug("Doing task %s with priority %d: render video %s for user %s (%s)" % (
                    task.id, task.priority, video, user.id, user))
                video_url, composite_name = faviews.render_video_for_user(user, video)
                logger.debug("Done task %s with priority %d: render video %s for user %s (%s) URL: %s" % (
                    task.id, task.priority, video, user.id, user, video_url))
                if video_url == Status.FAIL:
                    print('damn this error')
                    task.priority = 0
                    task.save()
                else:
                    faviews.save_video_for_user(user, video, video_url)
                    task.delete()
                    faviews.notify_user_task_rendered(user, video, video_url)

        time.sleep(5)


class CustomObtainAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        response = super(CustomObtainAuthToken, self).post(request, *args, **kwargs)
        token = Token.objects.get(key=response.data['token'])
        return Response({'token': token.key, 'id': token.user_id})


class CartViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = CartSerializer
    queryset = Cart.objects.all()
    ordering_fields = '__all__'
    
    def perform_create(self, serializer):
        serializer.save()
        userid = serializer.data['user']
        videoid = serializer.data['video']
        if Account.objects.filter(pk=userid).exists():
            try:
                video = RawVideo.objects.get(pk=videoid)
            except:
                return JsonResponse({"status": "error", "message": "video %s doesn't exist" % videoid})

            user = Account.objects.get(pk=userid)
            user_remaining_credit = user.credit - video.credit
            if user_remaining_credit < 0:
                return JsonResponse({"status": "fail", "message": "insufficient credit to download" })
            else:
                user.credit = user_remaining_credit
                user.save()
        else:
            return JsonResponse({"status": "error", "message": "user %s doesn't exist" % userid})

    def destroy(self, request, *args, **kwargs):
        try:
            #print("Test")
            #print(kwargs['pk'])
            cartid = kwargs['pk']
            if Cart.objects.filter(pk=cartid).exists():
                cart = Cart.objects.get(pk=cartid)
                userid = cart.user.id
                videoid = cart.video.id
                try:
                    user = Account.objects.get(pk=userid)
                except:
                    return JsonResponse({"status": "error", "message": "user %s doesn't exist" % userid})

                try:
                    video = RawVideo.objects.get(pk=videoid)
                except:
                    print("error")
                    return JsonResponse({"status": "error", "message": "video %s doesn't exist" % videoid})

                user.credit += video.credit
                user.save()
            else:
                return JsonResponse({"status": "error", "message": "cart %s doesn't exist" % cartid})

            instance = self.get_object()
            self.perform_destroy(instance)
            return Response("Success.", status=status.HTTP_200_OK)
        except:
            return Response("Error", status=status.HTTP_400_BAD_REQUEST)



class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = CampaignSerializer
    queryset = Campaign.objects.all()


class DraftVideoViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = DraftVideoSerializer
    queryset = DraftVideo.objects.all()


class TemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = TemplateSerializer
    queryset = Template.objects.all()

class LiveReadViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = LiveReadSerializer
    queryset = LiveRead.objects.all()

class PublishableVideoViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = PublishableVideoSerializer
    queryset = PublishableVideo.objects.all()
