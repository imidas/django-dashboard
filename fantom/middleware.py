from django.utils.deprecation import MiddlewareMixin
from fantom.models import RawVideo, CustomizedVideo,Account,Cart

"""
Api middleware module
"""
class VideoCountMiddleware(MiddlewareMixin):
    """
    Provides full logging of requests and responses
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.
        try:
            if request.path.startswith('/media/composite_video') :
                video_url = request.path
                customized_video = CustomizedVideo.objects.filter(url=video_url).first()
                customized_video.video.num_downloads +=1
                if customized_video.downloaded is not True:
                    customized_video.downloaded = True
                customized_video.video.save()
        except Exception as e:
            pass

        return response