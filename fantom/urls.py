"""fantom URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib.staticfiles.views import serve

from rest_framework import routers
from rest_framework.authtoken import views as drfauthviews

from fantom.api import views as faviews
from . import views

# add viewset for facebook pages
router = routers.DefaultRouter()
router.register('FBPages', faviews.FBPageViewSet, 'FBPage')
router.register('series', faviews.SeriesViewSet, 'Series')
router.register('rawvideos', faviews.RawVideoViewSet, 'RawVideos')
router.register('customizedvideos', faviews.CustomizedVideoViewSet, 'CustomizedVideos')
router.register('tasksrender', faviews.TasksRenderViewSet, 'TasksRender')
router.register('subscriptions', faviews.SubscriptionViewSet, 'Subscription')
router.register('cart', faviews.CartViewSet,'Cart')
router.register('campaign', faviews.CampaignViewSet,'Campaign')
router.register('draftvideo', faviews.DraftVideoViewSet, 'DraftVideo')
router.register('template', faviews.TemplateViewSet,'Template')
router.register('liveread', faviews.LiveReadViewSet,'LiveRead')
router.register('publishablevideo', faviews.PublishableVideoViewSet,'PublishableVideo')

router.register('users', faviews.UserViewSet)
router.register('groups', faviews.GroupViewSet)



urlpatterns = [
    # path('',                        RedirectView.as_view(url=settings.STATIC_HOME), name="home"),
    path('',                                admin.site.urls),
    path('dashboard/',                      views.dashboard, name="dashboard"),
    path('home/',                           views.user_login, name="home"),
    path('login/',                          views.user_login, name="login"),
    path('logout/',                         views.user_logout, name="logout"),
    path('signup/',                         views.signup, name='signup'),
    path('upload2/',                        views.upload_video, name='upload2'),
    path('account_settings/',               views.user_settings, name='account_settings'),
    path('users/',                          views.users, name='users'),
    path('facebook_pages_for_user/',        views.facebook_pages_for_user),
    path('delete_facebook/',                views.delete_facebook),
    path('series_dashboard/',               views.view_series, name='series_dashboard'),
    path('video/<int:video_id>/',           views.view_video, name='view_video'),
    path('distribute/',                     views.distribute, name='distribute'),
    path('manage_campaign/<userid>/',       views.manage_campaign, name='manage_campaign'),
    path('download_video/<int:video_id>/',  views.download_video, name='download_video'),
    path('activate/<uidb64>/<token>/',      views.activate, name='activate'),

    # REST stuff
    path('api-auth/',                       include('rest_framework.urls')),
    # path('api-token-auth/',                 drfauthviews.obtain_auth_token), # overrode with version that returns userid
    path('api-token-auth/',                 faviews.CustomObtainAuthToken.as_view()),
    path('api/v1/',                         include(router.urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
