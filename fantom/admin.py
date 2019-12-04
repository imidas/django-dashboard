from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account, FBPage, VideoSeries, RawVideo, CustomizedVideo, TasksRender, Subscription, Cart, Campaign, \
    DraftVideo, Template, LiveRead, PublishableVideo
from django.contrib.admin.filters import AllValuesFieldListFilter, ChoicesFieldListFilter, RelatedFieldListFilter, RelatedOnlyFieldListFilter
from admin_numeric_filter.admin import NumericFilterModelAdmin, SingleNumericFilter, RangeNumericFilter, SliderNumericFilter
from fantom.api.CustomSlider import CustomSliderNumericFilter,CustomSliderNumericFilterAvgLength
from django.contrib.auth.models import Group
from fantom.forms import GroupAdminForm


class DropdownFilter(AllValuesFieldListFilter):
    template = "dropdown_filter.html"

class ChoiceDropdownFilter(ChoicesFieldListFilter):
    template = 'dropdown_filter.html'

class RelatedDropdownFilter(RelatedFieldListFilter):
    template = 'dropdown_filter.html'


class RelatedOnlyDropdownFilter(RelatedOnlyFieldListFilter):
    template = 'dropdown_filter.html'

admin.site.unregister(Group)

admin.site.register(Campaign)
admin.site.register(DraftVideo)
admin.site.register(Template)
admin.site.register(LiveRead)
admin.site.register(PublishableVideo)

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    # Use our custom form.
    form = GroupAdminForm
    # Filter permissions horizontal as well.
    filter_horizontal = ['permissions']


@admin.register(Account)
class AccountAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'business_name', 'zip_code', 'city', 'state', 'country')
    fieldsets = (
        ('Personal Details',
        #  {'fields': ('username', 'email', 'business_name', 'description', 'coupon_description', 'address1', 'address2', 'zip_code', 'city', 'state', 'country', 'dummy','credit')}),
        {'fields': ('username', 'email', 'business_name', 'description', 'coupon_description', 'address1', 'address2', 'zip_code', 'city', 'state', 'country', 'dummy')}),
        ('Media',
         {'fields': ('light_brand_logo', 'dark_brand_logo',
                     'first_insert',
                     'first_insert_audio',
                     'second_insert',
                     'second_insert_audio')}),
        ('Permission', {'fields': ('is_superuser', 'is_staff')}),
        ('Password Details', {'fields': ('password',)})
    )


@admin.register(FBPage)
class FBPage(admin.ModelAdmin):
    pass



@admin.register(VideoSeries)
class VideoSeries(NumericFilterModelAdmin):
    list_display = ('name', 'thumbnail', 'average_length', 'channels', 'hosts','description','delivered')
    list_filter = (
        ('hosts', DropdownFilter),
        ('channels', DropdownFilter),
        ('category', ChoiceDropdownFilter),
        ('average_length',CustomSliderNumericFilterAvgLength),
        ('min_recommended_age', CustomSliderNumericFilter), #using slider library to for the admin list filter
        ('gender', ChoiceDropdownFilter),
        ('content_stale', ChoiceDropdownFilter),
        ('delivered', ChoiceDropdownFilter),
    )

@admin.register(RawVideo)
class RawVideo(admin.ModelAdmin):
    # list_display = ('id', 'video', 'thumbnail_url', 'series', 'num_downloads', 'length', 'date_created', 'credit', 'logo_type', 'logo_placement')
    list_display = ('id', 'video', 'thumbnail_url', 'series', 'num_downloads', 'length', 'date_created', 'logo_type', 'logo_placement')
    list_filter = ('series',)

@admin.register(CustomizedVideo)
class CustomizedVideo(admin.ModelAdmin):
    list_display = ('id','user', 'video', 'url', 'notified')
    list_filter = ('user', 'video')


@admin.register(TasksRender)
class TasksRender(admin.ModelAdmin):
    list_display = ('user', 'video', 'priority', 'date_requested')
    list_filter = ('user', 'video', 'priority', 'date_requested')

@admin.register(Subscription)
class Subscription(admin.ModelAdmin):
    list_display = ('id', 'user', 'series', 'date_created')
    list_filter = ('user', 'series')

@admin.register(Cart)
class Cart(admin.ModelAdmin):
    list_display = ('id','user', 'video')
    list_filter = ('user', 'video')

