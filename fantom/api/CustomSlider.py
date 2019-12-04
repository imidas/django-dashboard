from django.contrib import admin
from admin_numeric_filter.admin import SliderNumericForm, RangeNumericForm
from django.contrib.admin.utils import reverse_field_path
from django.db.models.fields import DecimalField, FloatField, IntegerField, DurationField
from django.db.models import Max, Min
from fantom.models import VideoSeries
import datetime


class RangeNumericFilterCustom(admin.FieldListFilter):
    request = None
    parameter_name = None
    template = 'admin/filter_numeric_range.html'

    def __init__(self, field, request, params, model, model_admin, field_path):
        super().__init__(field, request, params, model, model_admin, field_path)

        if not isinstance(field, (DecimalField, IntegerField, FloatField, DurationField)):
            raise TypeError('Class {} is not supported for {}.'.format(type(self.field), self.__class__.__name__))

        self.request = request

        if self.parameter_name is None:
            self.parameter_name = self.field.name

        if self.parameter_name + '_from' in params:
            value = params.pop(self.parameter_name + '_from')
            self.used_parameters[self.parameter_name + '_from'] = value

        if self.parameter_name + '_to' in params:
            value = params.pop(self.parameter_name + '_to')
            self.used_parameters[self.parameter_name + '_to'] = value

    def queryset(self, request, queryset):
        filters = {}
        value_from = self.used_parameters.get(self.parameter_name + '_from', None)
        value_to = self.used_parameters.get(self.parameter_name + '_to', None)

        if self.parameter_name == "average_length":
            if value_from is not None and value_to is not None:
                return queryset.filter(average_length__gte=datetime.timedelta(seconds=int(value_from)), average_length__lte=datetime.timedelta(seconds=int(value_to)))
        else:
            if value_from is not None and value_from != '':
                filters.update({
                    self.parameter_name + '__gte': self.used_parameters.get(self.parameter_name + '_from', None),
                })

            if self.parameter_name == "min_recommended_age":
                if value_to is not None and value_to != '':
                    filters.update({
                        "max_recommended_age" + '__lte': self.used_parameters.get(self.parameter_name + '_to', None),
                    })
            else:
                if value_to is not None and value_to != '':
                    filters.update({
                        self.parameter_name + '__lte': self.used_parameters.get(self.parameter_name + '_to', None),
                    })


            return queryset.filter(**filters)

    def expected_parameters(self):
        return [
            '{}_from'.format(self.parameter_name),
            '{}_to'.format(self.parameter_name),
        ]

    def choices(self, changelist):
        return ({
            'request': self.request,
            'parameter_name': self.parameter_name,
            'form': RangeNumericForm(name=self.parameter_name, data={
                self.parameter_name + '_from': self.used_parameters.get(self.parameter_name + '_from', None),
                self.parameter_name + '_to': self.used_parameters.get(self.parameter_name + '_to', None),
            }),
        }, )


class CustomSliderNumericFilter(RangeNumericFilterCustom):
    MAX_DECIMALS = 7
    STEP = None

    template = 'custom_slider.html'
    field = None

    def __init__(self, field, request, params, model, model_admin, field_path):
        super().__init__(field, request, params, model, model_admin, field_path)

        self.field = field
        parent_model, reverse_path = reverse_field_path(model, field_path)

        if model == parent_model:
            self.q = model_admin.get_queryset(request)
        else:
            self.q = parent_model._default_manager.all()

    def choices(self, changelist):

        min_value = self.q.all().aggregate(
            min=Min(self.parameter_name)
        ).get('min', 0)

        max_value = VideoSeries.objects.all().aggregate(max=Max('max_recommended_age')).get('max',0)

        if isinstance(self.field, (FloatField, DecimalField)):
            decimals = self.MAX_DECIMALS
            step = self.STEP if self.STEP else self._get_min_step(self.MAX_DECIMALS)
        else:
            decimals = 0
            step = self.STEP if self.STEP else 1

        return ({
            'title': 'Recommended Age Range',
            'decimals': decimals,
            'step': step,
            'parameter_name': self.parameter_name,
            'request': self.request,
            'min': min_value,
            'max': max_value,
            'value_from': self.used_parameters.get(self.parameter_name + '_from', min_value),
            'value_to': self.used_parameters.get(self.parameter_name + '_to', max_value),
            'form': SliderNumericForm(name=self.parameter_name, data={
                self.parameter_name + '_from': self.used_parameters.get(self.parameter_name + '_from', min_value),
                self.parameter_name + '_to': self.used_parameters.get(self.parameter_name + '_to', max_value),
            })
        }, )

    def _get_min_step(self, precision):
        result_format = '{{:.{}f}}'.format(precision - 1)
        return float(result_format.format(0) + '1')



class CustomSliderNumericFilterAvgLength(RangeNumericFilterCustom):
    MAX_DECIMALS = 7
    STEP = None

    template = 'custom_slider.html'
    field = None

    def __init__(self, field, request, params, model, model_admin, field_path):
        super().__init__(field, request, params, model, model_admin, field_path)

        self.field = field
        parent_model, reverse_path = reverse_field_path(model, field_path)

        if model == parent_model:
            self.q = model_admin.get_queryset(request)
        else:
            self.q = parent_model._default_manager.all()

    def choices(self, changelist):
        total = self.q.all().count()

        min_value = self.q.all().aggregate(
            min=Min(self.parameter_name)
        ).get('min', 0)

        min_value_sec = self.get_sec(str(min_value))

        if total > 1:
            max_value = self.q.all().aggregate(
                max=Max(self.parameter_name)
            ).get('max', 0)
        else:
            max_value = None

        max_value_sec = self.get_sec(str(max_value))

        if isinstance(self.field, (FloatField, DecimalField)):
            decimals = self.MAX_DECIMALS
            step = self.STEP if self.STEP else self._get_min_step(self.MAX_DECIMALS)
        elif isinstance(self.field, DurationField):
            decimals = 0
            step = 30
        else:
            decimals = 0
            step = self.STEP if self.STEP else 1

        return ({
            'title': 'Average Length',
            'decimals': decimals,
            'step': step,
            'parameter_name': self.parameter_name,
            'request': self.request,
            'min': min_value_sec,
            'max': max_value_sec,
            'value_from': self.used_parameters.get(self.parameter_name + '_from', min_value_sec),
            'value_to': self.used_parameters.get(self.parameter_name + '_to', max_value_sec),
            'form': SliderNumericForm(name=self.parameter_name, data={
                self.parameter_name + '_from': self.used_parameters.get(self.parameter_name + '_from', min_value_sec),
                self.parameter_name + '_to': self.used_parameters.get(self.parameter_name + '_to', max_value_sec),
            })
        }, )

    def _get_min_step(self, precision):
        result_format = '{{:.{}f}}'.format(precision - 1)
        return float(result_format.format(0) + '1')

    def get_sec(self,time_str):
        """Get Seconds from time."""
        h, m, s = time_str.split(':')
        return int(h) * 3600 + int(m) * 60 + int(s)
