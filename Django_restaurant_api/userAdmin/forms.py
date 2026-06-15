from orders.models import Product, Category
from django import forms


class AddProductForm(forms.ModelForm):
    title = forms.CharField(
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. Jollof Rice with Chicken',
            'class': 'w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none transition-all'
        })
    )
    image = forms.ImageField(
        widget=forms.FileInput(attrs={
            'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer'
        })
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': 'Describe your product...',
            'rows': 4,
            'class': 'w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none transition-all resize-none'
        })
    )
    price = forms.CharField(
        widget=forms.NumberInput(attrs={
            'placeholder': '0.00',
            'class': 'w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none transition-all'
        })
    )
    in_stock = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-5 h-5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500'
        })
    )

    # In AddProductForm, add this field:
    category = forms.ModelChoiceField(
        queryset=Category.objects.none(),  # Will be filtered in __init__
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none transition-all bg-white appearance-none'
        })
    )

    class Meta:
        model = Product
        fields = ['category', 'title', 'image', 'description', 'price', 'in_stock']


    def __init__(self, *args, **kwargs):
        # *args = positional arguments (like form data, files)
        # **kwargs = keyword arguments (like 'restaurant', 'instance', 'initial')
        
        # Pop 'restaurant' out of kwargs before passing to parent.
        # If 'restaurant' isn't in kwargs, default to None.
        restaurant = kwargs.pop('restaurant', None)
        # Example: kwargs was {'restaurant': restaurant_object, 'data': request.POST}
        # Now kwargs is {'data': request.POST} — restaurant is removed
        # restaurant variable now holds my_restaurant
        
        # Call the parent class's __init__ with the remaining kwargs.
        # This does all the normal form setup (building fields, binding data, etc.)
        super().__init__(*args, **kwargs)
        # At this point, self.fields['category'] exists and has ALL categories
        
        # If a restaurant was passed in, filter the category dropdown
        if restaurant:
            # Replace the queryset for the 'category' field
            # So the dropdown only shows categories belonging to this restaurant
            self.fields['category'].queryset = Category.objects.filter(restaurant=restaurant)
            # Example: If restaurant is "MamaPut", the dropdown only shows
            # categories that MamaPut created, not other restaurants' categories



from django import forms
from orders.models import Category


class AddCategoryForm(forms.ModelForm):
    """Form for creating a category. Shows different fields based on business type."""

    title = forms.CharField(
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. Small Chops, Jollof Rice',
            'class': 'w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none transition-all'
        })
    )
    
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer'
        })
    )

    # Prep time — only for restaurants
    prep_time_minutes = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'placeholder': 'e.g. 30',
            'class': 'w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none transition-all'
        })
    )

    # Prep days — only for vendors
    prep_day = forms.ChoiceField(
        required=False,
        choices=[
            (0, 'Same Day'),
            (1, '1 Day'),
            (2, '2 Days'),
            (3, '3 Days'),
            (4, '4 Days'),
            (5, '5 Days'),
            (6, '6 Days'),
            (7, '7 Days'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none transition-all bg-white'
        })
    )

    class Meta:
        model = Category
        fields = ['title', 'image', 'prep_time_minutes', 'prep_day']

    def __init__(self, *args, **kwargs):
        # Pop our custom keyword arguments before parent __init__
        self.restaurant = kwargs.pop('restaurant', None)
        self.business_type = kwargs.pop('business_type', None)
        super().__init__(*args, **kwargs)

        # ---------- Remove fields based on business type ----------
        if self.business_type in ('restaurant', 'hotel'):
            # Restaurants only need prep_time_minutes
            self.fields.pop('prep_day')

        elif self.business_type == 'vendor':
            # Vendors only need prep_day
            self.fields.pop('prep_time_minutes')

    def clean(self):
        """Validate based on business type."""
        cleaned_data = super().clean()
        business_type = self.business_type

        # ---------- Restaurant validation ----------
        if business_type in ('restaurant', 'hotel'):
            prep_time = cleaned_data.get('prep_time_minutes')
            if not prep_time:
                self.add_error(
                    'prep_time_minutes',
                    'Preparation time is required for restaurants.'
                )

        # ---------- Vendor validation ----------
        elif business_type == 'vendor':
            prep_day = cleaned_data.get('prep_day')
            if prep_day is None or prep_day == '':
                self.add_error(
                    'prep_day',
                    'Preparation days is required for vendors.'
                )

        return cleaned_data

    def save(self, commit=True):
        """Link the category to the restaurant before saving."""
        category = super().save(commit=False)
        category.restaurant = self.restaurant

        # ---------- Clear irrelevant fields based on business type ----------
        if self.business_type in ('restaurant', 'hotel'):
            # Restaurants don't use prep_day
            category.prep_day = None

        elif self.business_type == 'vendor':
            # Vendors don't use prep_time_minutes
            category.prep_time_minutes = None

        if commit:
            category.save()
        return category


