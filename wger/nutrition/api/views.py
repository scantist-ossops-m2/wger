# -*- coding: utf-8 -*-

# This file is part of wger Workout Manager.
#
# wger Workout Manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# wger Workout Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Workout Manager.  If not, see <http://www.gnu.org/licenses/>.

# Standard Library
import logging

# Django
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

# Third Party
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

# wger
from wger.nutrition.api.filtersets import (
    IngredientFilterSet,
    LogItemFilterSet,
)
from wger.nutrition.api.serializers import (
    IngredientImageSerializer,
    IngredientInfoSerializer,
    IngredientSerializer,
    IngredientWeightUnitSerializer,
    LogItemSerializer,
    MealItemSerializer,
    MealSerializer,
    NutritionalValuesSerializer,
    NutritionPlanInfoSerializer,
    NutritionPlanSerializer,
    WeightUnitSerializer,
)
from wger.nutrition.forms import UnitChooserForm
from wger.nutrition.models import (
    Image,
    Ingredient,
    IngredientWeightUnit,
    LogItem,
    Meal,
    MealItem,
    NutritionPlan,
    WeightUnit,
)
from wger.utils.viewsets import WgerOwnerObjectModelViewSet


logger = logging.getLogger(__name__)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for ingredient objects. For a read-only endpoint with all
    the information of an ingredient, see /api/v2/ingredientinfo/
    """

    serializer_class = IngredientSerializer
    ordering_fields = '__all__'
    filterset_class = IngredientFilterSet
    queryset = Ingredient.objects.all()

    @method_decorator(cache_page(settings.WGER_SETTINGS['INGREDIENT_CACHE_TTL']))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=True)
    def get_values(self, request, pk):
        """
        Calculates the nutritional values for current ingredient and
        the given amount and unit.

        This function basically just performs a multiplication (in the model), and
        is a candidate to be moved to pure AJAX calls, however doing it like this
        keeps the logic nicely hidden and respects the DRY principle.
        """

        result = {
            'energy': 0,
            'protein': 0,
            'carbohydrates': 0,
            'carbohydrates_sugar': 0,
            'fat': 0,
            'fat_saturated': 0,
            'fiber': 0,
            'sodium': 0,
            'errors': [],
        }
        ingredient = self.get_object()

        form = UnitChooserForm(request.GET)

        if form.is_valid():
            # Create a temporary MealItem object
            if form.cleaned_data['unit']:
                unit_id = form.cleaned_data['unit'].id
            else:
                unit_id = None

            item = MealItem()
            item.ingredient = ingredient
            item.weight_unit_id = unit_id
            item.amount = form.cleaned_data['amount']

            result = item.get_nutritional_values().to_dict
        else:
            result['errors'] = form.errors

        return Response(result)


class IngredientInfoViewSet(IngredientViewSet):
    """
    Read-only info API endpoint for ingredient objects. Returns nested data
    structures for more easy parsing.
    """

    serializer_class = IngredientInfoSerializer


class ImageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for ingredient images
    """

    queryset = Image.objects.all()
    serializer_class = IngredientImageSerializer
    ordering_fields = '__all__'
    filterset_fields = ('uuid', 'ingredient_id', 'ingredient__uuid')

    @method_decorator(cache_page(settings.WGER_SETTINGS['INGREDIENT_CACHE_TTL']))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class WeightUnitViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for weight unit objects
    """

    queryset = WeightUnit.objects.all()
    serializer_class = WeightUnitSerializer
    ordering_fields = '__all__'
    filterset_fields = ('language', 'name')


class IngredientWeightUnitViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for many-to-many table ingredient-weight unit objects
    """

    queryset = IngredientWeightUnit.objects.all()
    serializer_class = IngredientWeightUnitSerializer
    ordering_fields = '__all__'
    filterset_fields = (
        'amount',
        'gram',
        'ingredient',
        'unit',
    )


class NutritionPlanViewSet(viewsets.ModelViewSet):
    """
    API endpoint for nutrition plan objects. For a read-only endpoint with all
    the information of nutritional plan(s), see /api/v2/nutritionplaninfo/
    """

    serializer_class = NutritionPlanSerializer
    is_private = True
    ordering_fields = '__all__'
    filterset_fields = (
        'creation_date',
        'description',
        'has_goal_calories',
    )

    def get_queryset(self):
        """
        Only allow access to appropriate objects
        """
        # REST API generation
        if getattr(self, 'swagger_fake_view', False):
            return NutritionPlan.objects.none()

        return NutritionPlan.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """
        Set the owner
        """
        serializer.save(user=self.request.user)

    @action(detail=True)
    def nutritional_values(self, request, pk):
        """
        Return an overview of the nutritional plan's values
        """
        serializer = NutritionalValuesSerializer(
            NutritionPlan.objects.get(pk=pk).get_nutritional_values()['total'],
        )
        return Response(serializer.data)


class NutritionPlanInfoViewSet(NutritionPlanViewSet):
    """
    Read-only info API endpoint for nutrition plan objects. Returns nested data
    structures for more easy parsing.
    """

    serializer_class = NutritionPlanInfoSerializer


class MealViewSet(WgerOwnerObjectModelViewSet):
    """
    API endpoint for meal objects
    """

    serializer_class = MealSerializer
    is_private = True
    ordering_fields = '__all__'
    filterset_fields = (
        'order',
        'plan',
        'time',
    )

    def get_queryset(self):
        """
        Only allow access to appropriate objects
        """
        # REST API generation
        if getattr(self, 'swagger_fake_view', False):
            return Meal.objects.none()

        return Meal.objects.filter(plan__user=self.request.user)

    def perform_create(self, serializer):
        """
        Set the order
        """
        serializer.save(order=1)

    def get_owner_objects(self):
        """
        Return objects to check for ownership permission
        """
        return [(NutritionPlan, 'plan')]

    @action(detail=True)
    def nutritional_values(self, request, pk):
        """
        Return an overview of the nutritional plan's values
        """
        serializer = NutritionalValuesSerializer(Meal.objects.get(pk=pk).get_nutritional_values())
        return Response(serializer.data)


class MealItemViewSet(WgerOwnerObjectModelViewSet):
    """
    API endpoint for meal item objects
    """

    serializer_class = MealItemSerializer
    is_private = True
    ordering_fields = '__all__'
    filterset_fields = (
        'amount',
        'ingredient',
        'meal',
        'order',
        'weight_unit',
    )

    def get_queryset(self):
        """
        Only allow access to appropriate objects
        """
        # REST API generation
        if getattr(self, 'swagger_fake_view', False):
            return MealItem.objects.none()

        return MealItem.objects.filter(meal__plan__user=self.request.user)

    def perform_create(self, serializer):
        """
        Set the order
        """
        serializer.save(order=1)

    def get_owner_objects(self):
        """
        Return objects to check for ownership permission
        """
        return [(Meal, 'meal')]

    @action(detail=True)
    def nutritional_values(self, request, pk):
        """
        Return an overview of the nutritional plan's values
        """
        return Response(MealItem.objects.get(pk=pk).get_nutritional_values())


class LogItemViewSet(WgerOwnerObjectModelViewSet):
    """
    API endpoint for a meal log item
    """

    serializer_class = LogItemSerializer
    is_private = True
    ordering_fields = '__all__'
    filterset_class = LogItemFilterSet

    def get_queryset(self):
        """
        Only allow access to appropriate objects
        """
        # REST API generation
        if getattr(self, 'swagger_fake_view', False):
            return LogItem.objects.none()

        return LogItem.objects.select_related('plan').filter(plan__user=self.request.user)

    def get_owner_objects(self):
        """
        Return objects to check for ownership permission
        """
        return [(NutritionPlan, 'plan'), (Meal, 'meal')]

    @action(detail=True)
    def nutritional_values(self, request, pk):
        """
        Return an overview of the nutritional plan's values
        """
        return Response(
            LogItem.objects.get(pk=pk, plan__user=self.request.user).get_nutritional_values()
        )
