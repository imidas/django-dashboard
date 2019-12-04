from django.core.mail import EmailMessage
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.template.loader import render_to_string
from django_countries.fields import CountryField
from localflavor.us.models import USStateField
from django.utils.html import format_html
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver


def user_directory_path_insert1(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'acct_settings/user_{0}/insert1_{1}'.format(instance.id, filename)


def user_directory_path_audio1(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'acct_settings/user_{0}/audio1_{1}'.format(instance.id, filename)


def user_directory_path_insert2(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'acct_settings/user_{0}/insert2_{1}'.format(instance.id, filename)


def user_directory_path_audio2(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'acct_settings/user_{0}/audio2_{1}'.format(instance.id, filename)


class Account(AbstractUser):
    email = models.CharField(max_length=254, unique=True, null=False)
    business_name = models.CharField(max_length=254)
    address1 = models.CharField(max_length=254)
    address2 = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=12)
    state = USStateField()
    city = models.CharField(max_length=254)
    country = CountryField(default='US')
    # logo = models.ImageField(upload_to=settings.LOGOS_ROOT, blank=True)
    light_brand_logo = models.ImageField(upload_to=settings.LOGOS_ROOT, blank=True)
    dark_brand_logo = models.ImageField(upload_to=settings.LOGOS_ROOT, blank=True)
    description = models.TextField()
    coupon_description = models.TextField(blank=True)
    # first_insert = models.FileField(upload_to=settings.LOGOS_ROOT, blank=True)
    first_insert = models.FileField(upload_to=user_directory_path_insert1, blank=True)
    first_insert_audio = models.FileField(upload_to=user_directory_path_audio1, blank=True)
    second_insert = models.FileField(upload_to=user_directory_path_insert2, blank=True)
    second_insert_audio = models.FileField(upload_to=user_directory_path_audio2, blank=True)
    credit = models.IntegerField(default=1)
    client = models.CharField(max_length=256, blank=True)
    first_name = models.CharField(max_length=256, blank=True)
    last_name = models.CharField(max_length=256, blank=True)
    dummy = models.BooleanField(default=False)

    # old_password = models.CharField(max_length=256)
    # new_password = models.CharField(max_length=256)

    def __str__(self):
        return self.username

    def eligible(self):
        """
        Returns: eligible for rendering a video, only if has logo and inserts

        """
        eligible_user = True
        if not self.light_brand_logo and not self.dark_brand_logo:
            eligible_user = False
        if not self.first_insert:
            eligible_user = False
        # return bool(self.light_brand_logo) or bool(self.dark_brand_logo) and bool(self.first_insert)
        return eligible_user

    def downloadable(self):
        """

        Returns:  downloadable for a video , only if account isn't dummy
        """
        return not self.dummy

    class Meta:
        verbose_name = 'Account'


class FBPage(models.Model):
    """ Connects a user (on test) to a FB user, and a single FB page owned by this user. Store permanent page access token."""
    owner = models.ForeignKey(Account, on_delete=models.CASCADE)
    fb_userID = models.CharField(max_length=50)
    fb_pageID = models.CharField(max_length=50)
    fb_pageName = models.CharField(max_length=256)
    fb_pageAccessToken = models.CharField(max_length=256)
    token_expiration = models.DateTimeField(default=None, null=True)
    added_timestamp = models.DateTimeField(default=None, null=True)

    def __str__(self):
        return "user #%s (%s) -> %s (page %s)" % (self.owner.id, self.owner.username, self.fb_pageName, self.fb_pageID)

    def json(self):
        return {
            'fb_userID': self.fb_userID,
            'fb_pageID': self.fb_pageID,
            'fb_pageName': self.fb_pageName,
            'expiration': self.token_expiration
        }


class VideoSeries(models.Model):
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
    )

    CATEGORY_CHOICES = (
        ('Celebrity', 'Celebrity'),
        ('Finance', 'Finance'),
        ('Sports', 'Sports'),
        ('Travel', 'Travel'),
        ('Parenting', 'Parenting'),
        ('Beauty', 'Beauty'),
        ('Fitness', 'Fitness'),
        ('Gambling', 'Gambling'),
        ('Engineering', 'Engineering'),
        ('DIY', 'DIY'),
        ('Food', 'Food'),
    )

    DELIVERED_CHOICES = (
        ('Daily', 'Daily'),
        ('Bi-Weekly', 'Bi-Weekly'),
        ('Weekly', 'Weekly'),
        ('Other', 'Other'),
    )

    name = models.CharField(max_length=256)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    hosts = models.CharField(max_length=256)
    channels = models.CharField(max_length=256) #equal to format
    delivered = models.CharField(max_length=256,choices=DELIVERED_CHOICES, default='Daily')
    description = models.TextField()
    average_length = models.DurationField()  # ARIEL TODO CHECK
    topics = models.CharField(max_length=256)
    min_recommended_age = models.PositiveIntegerField(default=25,validators=[MaxValueValidator(99), MinValueValidator(12)])
    max_recommended_age = models.PositiveIntegerField(default=30,validators=[MaxValueValidator(99), MinValueValidator(12)])
    thumbnail = models.ImageField(upload_to=settings.LOGOS_ROOT)  # ARIEL TODO CHECK
    about_the_creator = models.TextField()
    editable = models.BooleanField()

    CONTENT_STALE_CHOICES = (
        ('evergreen', 'evergreen'),
        ('news', 'news'),
    )
    content_stale = models.CharField(max_length=20, choices=CONTENT_STALE_CHOICES, default='evergreen')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='Finance')

    def __str__(self):
        return self.name


MAX_SIZE = [150, 150]


class RawVideo(models.Model):
    video = models.FileField(upload_to=settings.LOGOS_ROOT)  # ARIEL TODO CHECK
    title = models.TextField(max_length=256, blank=True)
    thumbnail = models.ImageField(upload_to=settings.LOGOS_ROOT)  # ARIEL TODO CHECK
    length = models.PositiveIntegerField()  # in seconds
    dim_x = models.PositiveIntegerField()
    dim_y = models.PositiveIntegerField()
    description = models.TextField()
    date_created = models.DateTimeField(default=timezone.now)
    sports = models.CharField(max_length=256, blank=True)
    insert_time_1 = models.CharField(max_length=100, blank=True,
                                     help_text="Format is hours:minutes:seconds:frames",
                                     default='00:00:12:00')
    series = models.ForeignKey(VideoSeries, on_delete=models.CASCADE, related_name='raw_videos')
    hosts = models.CharField(max_length=256, blank=True)
    num_downloads = models.PositiveIntegerField(default=0)
    social_copy = models.TextField(blank=True)
    projected_score = models.FloatField(default=100.0)
    tags = models.CharField(max_length=256, blank=True)
    credit = models.IntegerField(default=1)

    LOGO_TYPE = (
        ('dark', 'dark'),
        ('light', 'light'),
    )
    logo_type = models.CharField(max_length=20, choices=LOGO_TYPE, default='dark')

    LOGO_PLACEMENT_CHOICES = (
        ('top_left', 'top_left'),
        ('top_right', 'top_right'),
        ('bottom_left', 'bottom_left'),
        ('bottom_right', 'bottom_right'),
    )
    logo_placement = models.CharField(max_length=20, choices=LOGO_PLACEMENT_CHOICES, default='bottom_left')

    def image_url(self):
        if self.image and hasattr(self.image, 'url'):
            return self.image.url

    @property
    def thumbnail_url(self):
        try:
            if bool(self.thumbnail):
                return format_html('<img src="%s" style="max-width:%spx; max-height:%spx;"/>' %
                                   (self.thumbnail.url, *MAX_SIZE))
            else:
                return None
        except:
            print("Video %s has an issue with the thumbnail. %s" % (self.id, self))
            return None

    def __str__(self):
        return str(self.id)


class CustomizedVideo(models.Model):
    url = models.CharField(max_length=1024)
    video = models.ForeignKey(RawVideo, on_delete=models.CASCADE)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    notified = models.BooleanField(default=False)
    downloaded = models.BooleanField(default=False)
    date_rendered = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return str(self.id)


class TasksRender(models.Model):
    video = models.ForeignKey(RawVideo, on_delete=models.CASCADE)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    priority = models.IntegerField(default=5)
    date_requested = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return str(self.id)


class Subscription(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    series = models.ForeignKey(VideoSeries, on_delete=models.CASCADE)
    date_created = models.DateTimeField(default=timezone.now)


class Cart(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    video = models.ForeignKey(RawVideo, on_delete=None)

    def __str__(self):
        return str(self.id)


class Campaign(models.Model):
    """Compaing model for adding and retriveing compaings"""

    name = models.CharField(max_length=255)
    url = models.CharField(max_length=1024)
    dark_logo = models.FileField(upload_to='dark_logo/')
    light_logo = models.FileField(upload_to='dark_logo/')
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    on_screen_offer = models.CharField(max_length=255, blank=True, null=True)
    campaign_live_read = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return str(self.name)


class DraftVideo(models.Model):
    """Video Model for uploading videos"""

    ASPECT_RATIO_CHOICES = (
        ('4:3', '4:3'),
        ('16:9', '16:9'),
        ('9:16', '9:16'),
        ('N/A', 'N/A')
    )

    video = models.FileField(upload_to='videos/')
    aspect_ratio = models.CharField(max_length=255,null=True, blank=True, choices=ASPECT_RATIO_CHOICES)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    title = models.CharField(max_length=255,null=True, blank=True)
    thumbnail_image = models.ImageField(blank=True, null=True)

    def __str__(self):
        return str(self.video)


class LiveRead(models.Model):
    """Live read model"""

    title = models.CharField(max_length=255, blank=True, null=True)
    url = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return str(self.title)


class Template(models.Model):

    TYPE_CHOICES = (
        ('Basic', 'Basic'),
        ('Advanced', 'Advanced'),
        ('Custom', 'Custom'),
    )

    type = models.CharField(max_length=255, choices=TYPE_CHOICES, blank=True)
    title = models.CharField(max_length=255, )
    desktop_video_url = models.URLField()
    desktop_video_thumbnail = models.URLField()
    phone_video_url = models.URLField()
    phone_video_thumbnail = models.URLField()
    tablet_video_url = models.URLField()
    tablet_video_thumbnail = models.URLField()


    def __str__(self):
        return str(self.title)

class PublishableVideo(models.Model):

    LOGO_PLACEMENT_CHOICES=(
        ('top_left', 'top_left'),
        ('top_right', 'top_right'),
        ('bottom_left', 'bottom_left'),
        ('bottom_right', 'bottom_right'),
    )

    LOGO_TYPE_CHOICES=(
        ('dark', 'dark'),
        ('light', 'light')
    )

    draft_video = models.ForeignKey(DraftVideo, on_delete=models.CASCADE)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    logo_placement = models.CharField(max_length=20, choices=LOGO_PLACEMENT_CHOICES, blank=True, null=True)
    logo_type = models.CharField(max_length=10, choices=LOGO_TYPE_CHOICES)
    template = models.ForeignKey(Template, on_delete=models.CASCADE)
    live_read = models.ForeignKey(LiveRead, on_delete=models.CASCADE, blank=True, null=True)
    use_campaign_live_read = models.BooleanField(default=False)

@receiver(post_save, sender=PublishableVideo)
def send_email_handler(sender, instance: PublishableVideo, created: bool, **kwargs):
    if created:
        # send email to the admin
        mail_subject = 'New publishable video.'
        message = render_to_string('new_publishable_video.html', {
            'publishable_video': instance,
            'live_read_title': instance.live_read.title if bool(instance.live_read) else 'No Live-read',
            'logo_placement': instance.logo_placement if bool(instance.logo_placement) else 'No Position'
        })
        to_email = ['sairamtummala1947@gmail.com', ]
        email = EmailMessage(
            mail_subject, message, to=to_email
        )
        email.send()