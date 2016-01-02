from django.conf.urls.defaults import *
from django.views.generic import DetailView
from presta.forms import LoadDataForm, AddProductsShopForm

from presta.models import Shop

urlpatterns = patterns('presta.views',
    url('^get_data$', 'get_data', name='get_data'),
    url('^get_data_paginated/(?P<page>\d+)$', 'get_data_paginated', name='get_data_paginated'),
    url('^update$', 'update_data', name='update_data'),
    url('^check_update', 'check_update', name='check_update'),
    url('^update_single$', 'update_data_single', name='update_data_single'),
    url('^save_csv$', 'save_csv', name='save_csv'),
    url('^save_csv_api$', 'save_csv', name='save_csv_api'),
    url('^add_shop$', 'add_shop', name='add_shop'),
    url('^temp_shop_save$', 'temp_shop_save', name='temp_shop_save'),
    url('^update_shops$', 'update_shops', name='update_shops'),
    url('^load_shop/(?P<pk>\d+)$', 'load_shop', name='load_shop'),
    url('^load_form', 'load_shop', name='load_form'),

    url('^upload_update_csv$', 'upload_csv', {'form_class': LoadDataForm}, name='upload_update_csv'),
    url('^upload_add_csv$', 'upload_csv', {'form_class': AddProductsShopForm}, name='upload_add_csv'),
    url('^clear_update_csv$', 'clear_csv', {'form_class': LoadDataForm}, name='clear_update_csv'),
    url('^clear_add_csv$', 'clear_csv', {'form_class': AddProductsShopForm}, name='clear_add_csv'),

    url('^shop_row/(?P<pk>\d+)$', DetailView.as_view(context_object_name="shop",
                                                     model=Shop,
                                                     template_name='partial/shop_row.html'),
                                                     name='shop_row'),
    url('^shop_edit/(?P<pk>\d+)$', 'shop_edit', name='shop_edit'),
    url('^shop_status/(?P<pk>\d+)$', 'shop_status', name='shop_status'),
    url('^shop_delete/(?P<pk>\d+)$', 'shop_delete', name='shop_delete'),
    url('^shop_add_data/(?P<pk>\d+)$', 'add_data', name='add_data'),
    url('^add_images/(?P<product_id>\d+)$', 'add_images', name='add_images'),
    url('^remove_images/(?P<product_id>\d+)$', 'remove_images', name='remove_images'),
)

# Module integration
urlpatterns += patterns('presta.views',
    url('^module_activate/$', 'module_activate', name='module_activate'),
)
