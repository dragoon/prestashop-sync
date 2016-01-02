function update_button_state()  {
    if ($('table.sync-data tbody input:checkbox:checked').length == 0) {
        $('.btn.update').addClass('disabled');
    }
    else {
        $('.btn.update').removeClass('disabled');
    }

    $('table.sync-data tbody tr').removeClass('hover');
    $('table.sync-data tbody tr:has(input:checkbox:checked)').addClass('hover');
}

function check_update_finished() {
    var $form = $('#load_data_form');
    $.post($form.attr('data-update-url'), $form.formToArray(), function(data){
        if (data['result'] == 'success') {
            $form.find('input.link-button').removeClass('pressed');
            open_ok_dialog($('span#updated_text').text());
            removeUpdateCSVFile();
        }
        else if (data['result'] == 'wait') {
            setTimeout(check_update_finished, 2000);
        }
    }, 'json');
}

function parse_domain(domain) {
    if (domain.indexOf('http://') === 0){
        domain = domain.slice(7)
    }
    else if (domain.indexOf('https://')===0) {
        domain = domain.slice(8)
    }
    var i = domain.indexOf('/');
    if (i>0) {
        domain = domain.slice(0, i);
    }
    return domain;
}

function update_battery() {
    var battery = $('.battery.label');
    if (battery.length) {
        $.get(battery.attr('data-url'), function(data) {
            battery.remove();
            $('.inset-block').prepend($(data));
        });
    }
}

function load_shop_data(btn) {
    open_loading();
    btn.addClass('pressed');
    var domain = $('#load_data_form input[name=domain]').val();

    $.post(btn.attr('href'),
        {'domain': domain,
         'sync_type': $('#load_data_form select[name=sync_type]').val(),
         'key': $('#load_data_form input[name=key]').val()},
        function(data, textStatus, jqXHR) {
            btn.removeClass('pressed');
            $('#load_data_form .error').remove();
            if (data['result'] == 'success') {
                if (data['temp']) {
                    $('#save_shop_question span').text(parse_domain(domain));
                    $('#save_shop_question').fadeIn();
                }
                $('#products_table').html(data['response']);
                $('.update-button-wrapper').show();
                $('.form-header.header3').show();
                var bodyelem;
                if($.browser.safari){ bodyelem = $("body") } else{ bodyelem = $("html") }
                bodyelem.animate({scrollTop: $('#products_table').offset().top-50}, 1000);
            }
            else if (data['result'] == 'error') {
                display_form_errors(data['response'], $('#load_data_form'));
            }
            close_loading();
        }, 'json');
        return false;
}

$(document).ready(function() {
    // bind facebox forms (login, dialogs, etc..)
    $('a[rel*=facebox]').facebox();

    // bind special facebox close on all cancel buttons
    $('.facebox-close').live('mousedown', function() {
        $(document).trigger('close.facebox');
    });

    $('.help-link').live('click', function(){
        return false;
    });

    $('#load_data').live('click', function() {
        reachGoal('LOAD_DATA', 'Load data', 'User pressed load data button');
        return load_shop_data($(this));
    });

    $('#load_data_demo').live('click', function() {
        reachGoal('DEMO_LOAD', 'Demo load data', 'User pressed load demo data button');
        return load_shop_data($(this));
    });

    $('#save_shop_question button:first').click(function() {
        open_loading();
        $.post($(this).attr('data-href'), {}, function (shop_id){
            $('#save_shop_question').fadeOut();
            var url = '/shop_row/'+shop_id;
            $.get(url, function(data) {
                $('table.shop-table tbody').append(data);
                close_loading();
                update_shops_formset();
            });
        });
        return false;
    });
    $('#save_shop_question button:last').click(function() {
        $('#save_shop_question').fadeOut();
        return false;
    });

    $('.pagination a:not(.current)').live('click', function(){
        return load_shop_data($(this));
    });

    // demo button change on domain change
    $('#load_data_form input[name=domain]').live('keyup', function(){
        if ($(this).val()!='presta-test.com/' && $('#load_data_demo:visible').length)
        {
            $('#load_data_demo').hide();
            $('#load_data').show();
        }
        if ($(this).val()=='presta-test.com/' && $('#load_data_demo:hidden').length)
        {
            $('#load_data_demo').show();
            $('#load_data').hide();
        }
    });

    // Bind forbidden first if needed
    $('span.btn.update, #update_data').live('click', function(e){
        if ($('#battery_exhausted_watermark').length) {
            e.stopImmediatePropagation();
            e.preventDefault();
            open_ok_dialog($('span#please_upgrade').text());
            return;
        }
    });

    // bulk update
    $('#load_data_form #update_data').live('click', function(){
        reachGoal('UPDATE_DATA_BULK');
        $('#load_data_form').ajaxSubmit({
            beforeSubmit: function(formData, $form, options) {
                open_loading();
                $form.find('.error').remove();
                $form.find('input.link-button').addClass('pressed');
            },
            success: function(data, statusText, xhr, $form) {
                if (data['result']=='error'){
                    display_form_errors(data['response'], $form);
                    $form.find('input.link-button').removeClass('pressed');
                    close_loading();
                }
                else
                    check_update_finished();
                    update_battery();
            },
            dataType: 'json'
        });
        return false;
    });

    // Sey key dialog
    $('.toggle-password').live('click', function(){
        var klass = $(this).attr('data-target-class');
        var parent = $(this).parent();
        var hidden = parent.find('input.'+klass+':hidden');
        var visible = parent.find('input.'+klass+':visible');
        visible.toggle();
        hidden.val(visible.val()).toggle().attr('name', visible.attr('name'));
        visible.removeAttr('name');
        return false;
    });

    $("#load_data_form a.help-link").tooltip();

    // START: update custom actions --------------------------------
    $('table.sync-data input.all:checkbox').live('click', function(){
        $('table.sync-data tbody input:checkbox').attr('checked', !!$(this).attr('checked'));
        update_button_state();
    });

    $('table.sync-data tbody tr').live('click', function(){
        var $checkbox = $(this).find(':checkbox');
        $checkbox.attr('checked', !$checkbox.attr('checked'));
        update_button_state();
    });

    // Stop usual event propagation
    $('table.sync-data tbody input:checkbox').live('click', function(event) {
        event.stopPropagation();
        update_button_state();
    });

    $('table.sync-data tbody input[type="number"]').live('click', function(event) {
        if ($(this).parents('tr').find('input:checkbox:checked').length) {
            event.stopPropagation();
        }
    });

    // Show fixed update button on scroll
    $(window).scroll(function() {
        if ($('.update-button-wrapper').length && !isScrolledDownIntoView('.update-button-wrapper')){
            $('.update-panel').addClass('fixed');
            $(".update-panel").fadeIn("fast");
        }
        else if ($('.update-panel').hasClass('fixed')) {
            $('.update-panel').removeClass('fixed').removeAttr('style');
        }
    });

    //END: update custom actions --------------------------------------------

    // update single action
    $('span.btn.update').live('click',function(){
        reachGoal('UPDATE_DATA_SINGLE');
        var button = $(this);
        var updateInfo = button.find('.update-info');
        updateInfo.empty();
        button.find('.update-text').hide();
        updateInfo.append('<img src="/static/images/update-loader.gif">');
        button.addClass('pressed');
        var data = {domain: $('#load_data_form input[name=domain]').val(),
                    sync_type: $('#load_data_form select[name=sync_type]').val(),
                    key: $('#load_data_form input[name=key]').val()};
        $('table.sync-data tbody tr:first td:last input').each(function(){
                data[$(this).attr('name')]=[];
        });

        $('table.sync-data tbody input:checkbox:checked').each(function(){
            $(this).parents('tr').find('td:last input').each(function() {
                data[$(this).attr('name')].push($(this).attr('value'));
            });
        });

        $.post($('#products_table form').attr('action'), data, function(result){
            updateInfo.empty();

            // return if old api file
            if (result['response']!="update_ok") {
                open_ok_dialog($('span#'+result['response']).html());
                button.find('.update-text').show();
                button.removeClass('pressed');
                return;
            }
            updateInfo.append('<img src="/static/images/ok.png">');
            setTimeout( function() {
                updateInfo.children().fadeOut('slow', function() {
                    $(this).empty();
                    button.find('.update-text').show();
                    button.removeClass('pressed');
                    $('table.sync-data tbody input:checkbox').removeAttr('checked');
                    update_button_state();
                });
            }, 1000);
            update_battery();
        }, 'json');
    });

    // bind dismiss user message
    $('span.dismiss-message').live('click', function() {
        var li = $(this).parent().parent();
        li.slideUp('fast', function() {
            li.remove();
            if (!$('ul.messages li').length)
                $('ul.messages').remove();
        });
        return false;
    });

    // free plan change to upgrade link
    $('#free_plan').live('mouseenter', function() {
        $(this).removeClass('label-warning').addClass('label-success').text($('#upgrade_plan_text').text());
    }).live('mouseleave', function() {
        $(this).removeClass('label-success').addClass('label-warning').text($('#free_plan_text').text());
    });

});
