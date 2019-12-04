import os
from django.conf import settings
from django.contrib.auth.models import Group
from fantom.models import Account, FBPage, VideoSeries, RawVideo, CustomizedVideo, TasksRender, Subscription, Cart, \
    Campaign, DraftVideo, PublishableVideo, Template, LiveRead
from rest_framework import serializers
from django_filters.rest_framework import BaseRangeFilter,NumberFilter
from supportfiles.pymediainfo import MediaInfo
import ffmpeg
from pathlib import Path
import os

class UserSerializer(serializers.HyperlinkedModelSerializer):
    groups = serializers.StringRelatedField(many=True, read_only=True)
    class Meta:
        model = Account
        fields = ['id',
                  'business_name',
                  'username',
                  'email',
                  'url',
                  'light_brand_logo',
                  'dark_brand_logo',
                  'first_insert',
                  'first_insert_audio',
                  'second_insert',
                  'second_insert_audio',
                  'address1',
                  'address2',
                  'zip_code',
                  'state',
                  'city',
                  'country',
                  'client',
                  'first_name',
                  'last_name',
                  'dummy',
                #   'credit',
                  'groups'
                  ]

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr == 'password':
                instance.set_password(value)
            else:
                setattr(instance, attr, value)
        instance.save()
        return instance

class PasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ['url', 'name']


class FBPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FBPage
        fields = ('owner', 'fb_userID', 'fb_pageID', 'fb_pageName')
        read_only_fields = ('owner',)


class NumberRangeFilter(BaseRangeFilter, NumberFilter):
    pass


class SeriesSerializer(serializers.ModelSerializer):
    #age__range = NumberRangeFilter(field_name='recommended_age', lookup_expr='range')
    class Meta:
        model = VideoSeries

        fields = (
            'id', 'name', 'hosts', 'channels', 'category', 'thumbnail', 'description', 'average_length', 'topics',
            'min_recommended_age','max_recommended_age','delivered', 'about_the_creator', 'raw_videos', 'editable', 'content_stale')

        depth = 1


class RawVideoSerializer(serializers.ModelSerializer):
    def validate_insert_time_1(self, value):
        try:
            times = [int(t) for t in value.split(":")]
        except:
            raise serializers.ValidationError("insert_time_1 format should be hours:minutes:seconds:frames")
        return value

    class Meta:
        model = RawVideo
        # fields = (
        #     'id', 'video', 'title', 'thumbnail', 'series', 'date_created', 'social_copy', 'insert_time_1', 'hosts',
        #     'description', 'sports', 'length', 'dim_x', 'dim_y', 'num_downloads', 'projected_score', 'tags','credit', 'logo_type', 'logo_placement')
        fields = (
            'id', 'video', 'title', 'thumbnail', 'series', 'date_created', 'social_copy', 'insert_time_1', 'hosts',
            'description', 'sports', 'length', 'dim_x', 'dim_y', 'num_downloads', 'projected_score', 'tags', 'logo_type', 'logo_placement')
        depth = 1


class CustomizedVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomizedVideo
        fields = ('id', 'url', 'video', 'user', 'notified', 'downloaded', 'date_rendered')
        # depth = 1


class TasksRenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = TasksRender
        fields = ('id', 'video', 'user', 'priority', 'date_requested')


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = '__all__'


class CartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cart
        fields = ('id', 'user', 'video')


class CampaignSerializer(serializers.ModelSerializer):
    """Campaign Serializer"""
    dark_logo = serializers.FileField(required=False)
    light_logo = serializers.FileField(required=False)
    
    class Meta:
        model = Campaign
        fields = ('id', 'user', 'name','url','light_logo','dark_logo', 'on_screen_offer', 'campaign_live_read')


class AspectRatio:
    @staticmethod
    def calculate_aspect(width, height):
            def gcd(a, b):
                """The GCD (greatest common divisor) is the highest number that evenly divides both width and height."""
                return a if b == 0 else gcd(b, a % b)

            r = gcd(width, height)
            x = int(width / r)
            y = int(height / r)

            return f"{x}:{y}"


class DraftVideoSerializer(serializers.ModelSerializer):
    """Video Serializer"""
    aspect_ratio = serializers.SerializerMethodField()

    def get_aspect_ratio(self, obj):
    
        media_info = MediaInfo.parse(os.path.join(settings.MEDIA_ROOT, str(obj.video)))
        for track in media_info.tracks:
            if track.track_type == 'Video':
                return AspectRatio.calculate_aspect(track.width,track.height)

    # def create(self, validated_data):
    #     instance = super(DraftVideoSerializer, self).create(validated_data)
    #     video_name = Path(os.path.basename(instance.video.path)).stem
    #     thumbnail_path='media/videos/'+video_name+'_thumbnail.png'
    #     TAKE_SCREENSHOT_AFTER_SECONDS=2
    #     try:
    #         ffmpeg.input(instance.video.path, ss=TAKE_SCREENSHOT_AFTER_SECONDS).output(
    #             thumbnail_path, vframes=1).overwrite_output().run(
    #             capture_stdout=True, capture_stderr=True)
    #     except ffmpeg.Error as e:
    #         print('stdout:', e.stdout.decode('utf8'))
    #         print('stderr:', e.stderr.decode('utf8'))
    #         raise e
    #     instance.thumbnail_image = 'videos/'+video_name+'_thumbnail.png'
    #     instance.save()
    #     return instance

    class Meta:
        model = DraftVideo
        fields = ('id', 'user', 'video','aspect_ratio', 'title', 'thumbnail_image')


class TemplateSerializer(serializers.ModelSerializer):

    class Meta:
        model=Template
        fields=('id', 'type', 'title', 'desktop_video_url', 'desktop_video_thumbnail', 'phone_video_url',
                'phone_video_thumbnail', 'tablet_video_url', 'tablet_video_thumbnail',)


class LiveReadSerializer(serializers.ModelSerializer):

    class Meta:
        model=LiveRead
        fields=('id','title','url',)


class PublishableVideoSerializer(serializers.ModelSerializer):

    class Meta:
        model = PublishableVideo
        fields = ('id', 'draft_video', 'campaign', 'logo_placement', 'logo_type', 'template', 'live_read',)