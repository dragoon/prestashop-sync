function base_status(shop_id, func) {
    var status_td = $('table.shop-table tr#shop_'+shop_id+' td.status');
    var angle = 0;
    var update_icon = status_td.find('a.update');
    var rotateId = setInterval(function(){
        angle+=5;
        update_icon.rotate(angle);
    },17);
    func(update_icon.attr('href'), function(data) {
        update_icon.removeClass('red green');
        update_icon.addClass(data[0]);
        clearInterval(rotateId);
        update_icon.rotate(0);
        if (data[1]){
            // Need this manipulation for tooltip
            var a = status_td.find('a:last').clone();
            status_td.find('a:last').remove();
            status_td.append(a);
            a.attr('title', data[1]);
            status_td.find('a:last').show();
            status_td.find('a:last[title]').tooltip({tipClass:'shoptooltip'});
        }
        else {
            var update_img = $('<img src="/static/images/status/ok.png">');
            update_icon.hide();
            status_td.append(update_img);
            setTimeout( function() {
                update_img.fadeOut('slow', function() {
                    update_img.remove();
                    update_icon.show();
                });
            }, 1000);
            status_td.find('a:last').hide();
        }
    }, 'json');
}

function get_status(shop_id) {
    return base_status(shop_id, $.get)
}

function update_status(shop_id) {
    return base_status(shop_id, $.post)
}

function update_shops_formset() {
    // Updates hidden form containing all shops
    $('#update_shops_form').parent().load($('#update_shops_form').attr('action'));
}

$(function() {

    // please register dialog
    $('#please_register_dialog').live('click', function() {
        open_ok_dialog($('span#please_register').text());
        return false;
    });

    // Add shop form
    $('form.shop-form').live('submit', function() {
        $('#facebox form.shop-form').ajaxSubmit({
            beforeSubmit: before_submit,
            success: function(data, statusText, xhr, $form) {
                $form.find('.error').remove();
                after_submit($form);
                if (data['result'] == 'success') {
                    open_loading();
                    var shop_id = data['response'];
                    var url = '/shop_row/'+shop_id;
                    $.get(url, function(data) {
                        $('table.shop-table tbody').append(data);
                        get_status(shop_id);
                        close_loading();
                        update_shops_formset();
                    });
                }
                else if (data['result'] == 'error') {
                    display_form_errors(data['response'], $form);
                }
            },
            dataType: 'json'
        });
        return false;
    });

    // Update status button
    $('table.shop-table td.status a.update').live('click', function(){
        var shop_id = $(this).attr('data-shop');
        update_status(shop_id);
        return false;
    });

    // Delete shop button
    $('table.shop-table td.actions a.delete').live('click', function(){
        $('#delete_shop_message a').text($(this).parents('tr').find('td:first a.shop-load').text());
        $.facebox({ div: '#delete_shop_dialog' }, 'width-300');
        $('#facebox #delete_shop').attr('href', $(this).attr('href'));
        $('#facebox #delete_shop').attr('data-shop', $(this).attr('data-shop'));
        return false;
    });

    $('#facebox #delete_shop').live('click', function() {
        open_loading();
        var shop_id = $(this).attr('data-shop');
        $.post($(this).attr('href'), {}, function(){
            $('table.shop-table tr#shop_'+shop_id).remove();
            close_loading();
            update_shops_formset();
        });
        return false;
    });

    // Edit shop action button
    $('table.shop-table td.actions a.edit').live('click', function(){
        $.facebox({ ajax: $(this).attr('href') });
        return false;
    });

    // Add products button
    $('table.shop-table td.actions a.add').live('click', function(){
        reachGoal('ADD_PRODUCTS', 'Start adding products', 'User started adding products');
        $.facebox({ ajax: $(this).attr('href') });
        $(document).one('reveal.facebox', function() {
            var last = $('.add-shop-products-form div.row:last');
            var last_clone = last.clone();
            $('#empty_row').append(last_clone);
            $(".add-shop-products-form a.help-link").tooltip({tipClass:'shoptooltip', delay:300});
        });
        $(document).one('close.facebox', function(){
            $.post($('#add_products_csv').attr('data-clear-url'), {});
        });
        return false;
    });

    // Add more products
    $('.add-shop-products-form div.add-more a').live('click', function(){
        var cloned = $('#empty_row div.row').clone();
        var count = $('.add-shop-products-form #id_form-TOTAL_FORMS').val();
        cloned.find('#id_form-0-order').val(count);
        var cloned_html = cloned.html();

        // Replace form number in a clone
        cloned.html(cloned_html.replace(/form-0/g, 'form-'+count).replace(/images\/0/g, 'images/'+count));
        cloned.find('div.remove').css('display','block');
        $('.add-shop-products-form div.row:last').after(cloned);
        count++;
        $('.add-shop-products-form #id_form-TOTAL_FORMS').val(count);
        return false;
    });

    // Remove product
    $('.add-shop-products-form div.row div.remove a').live('click', function(){
        var count = $('.add-shop-products-form #id_form-TOTAL_FORMS').val()-1;
        $('.add-shop-products-form #id_form-TOTAL_FORMS').val(count);
        $(this).parents('div.row').remove();
        return false;
    });

    //Submit add products form
    $('.add-shop-products-form .link-button').live('click', function(){
        $('.add-shop-products-form').ajaxSubmit({
            beforeSubmit: function(formData, $form, options) {
                before_submit(formData, $form, options);
                var input_count = $('#empty_row div.row :input').length;
                var j =1;
                for(var i = input_count+3;i<formData.length; i++){
                    if (i>(input_count+2+j*input_count))
                        j++;
                    formData[i].name='form-'+j+'-'+formData[i].name.split('-')[2];
                }
            },
            success: function(data, statusText, xhr, $form) {
                $form.find('.error').remove();
                if (data['result'] == 'success') {
                    open_ok_dialog($('span#'+data['response']).text());
                }
                else if (data['result'] == 'error') {
                    display_form_errors(data['response'], $form);
                }
                after_submit($form);
            },
            dataType: 'json'
        });
        return false;
    });

    $('#edit_shop_form .link-button').live('click', function() {
        $('#edit_shop_form').ajaxSubmit({
            beforeSubmit: before_submit,
            success: function(data, statusText, xhr, $form) {
                $form.find('.error').remove();
                if (data['result'] == 'success') {
                    // Update title and domain
                    var shop = $('table.shop-table').find('tr#shop_'+data['response']);
                    shop.find('a.shop-load').text($form.find('input#id_title').val());
                    shop.find('a.domain span').text($form.find('input#id_domain').val());

                    $(document).trigger('close.facebox');
                }
                else if (data['result'] == 'error') {
                    display_form_errors(data['response'], $form);
                }
                after_submit($form);
            },
            dataType: 'json'
        });
        return false;
    });

    // Load shop to main page
    $('table.shop-table a.shop-load').live('click', function(e) {
        load_main_form(this);
        e.preventDefault();
    });
});
