
function isScrolledDownIntoView(elem)
{
    var docViewTop = $(window).scrollTop();
    var docViewBottom = docViewTop + $(window).height();

    var elemTop = $(elem).offset().top;
    var elemBottom = elemTop + $(elem).height();

    return ((elemBottom >= docViewTop) && (elemTop >= docViewTop) );
}

function open_loading() {
    $.facebox({ div: '#loading_dialog' }, 'width-250');
    $('#facebox .close_image').hide(0);
}

function close_loading() {
    $(document).trigger('close.facebox');
    $('#facebox .close_image').show(1000);
}

function open_ok_dialog(text) {
    $.facebox({ div: '#ok_dialog' }, 'width-300');
    $("#facebox .content div").html(text);
    $('#facebox .close_image').show(0);
}

function load_main_form(obj) {
    open_loading();
    $('#load_data_form_wrapper').load($(obj).attr('href'), function() {
        if ($(obj).hasClass('shop-load')){
            $('#load_data_form').find('#main_buttons_wrapper a.btn-primary:visible').click();
        }
        //$("#load_data_form label a[title]").tooltip();
        //$('a[rel*=facebox]').facebox();
    });
}

function display_form_errors(errors, $form) {
    for (var k in errors) {
        if ($form.find('.custom-select select[name=' + k + ']').length) {
            $form.find('.custom-select:has(select[name=' + k + '])').after('<div class="error">' + errors[k] + '</div>');
        }
        else if ($form.find('.toggle-password').length && k==$form.find('.toggle-password').attr('data-target-class'))
            $form.find('.toggle-password').after('<div class="error">' + errors[k] + '</div>');
        else if (k == '__all__') {
            $form.find('input:not([type="submit"]):last').after('<div class="error">' + errors[k] + '</div>');
        }
        else {
            $form.find('input[name=' + k + ']').after('<div class="error">' + errors[k] + '</div>');
            $form.find('select[name=' + k + ']').after('<div class="error">' + errors[k] + '</div>');
        }
    }
}

function before_submit(formData, $form, options) {
    $form.find('.link-button').addClass('pressed');
    $form.find('.link-button').before('<img src="/static/images/update-loader.gif" class="loader">');
}

function after_submit($form) {
    $form.find('.link-button').removeClass('pressed').prev().remove();
}

$(document).ready(function() {
    $(document).bind('loading.facebox', function() {
        $(document).unbind('keydown.facebox');
        $('#facebox_overlay').unbind('click');
    });

    // Prevent default handlers on achors with "disabled" class
    $('a,span,input.link-button,.btn').live('click', function(e){
        if ($(this).hasClass('disabled') || $(this).hasClass('pressed')) {
            e.stopImmediatePropagation();
            e.preventDefault();
        }
    });

    $('select').live('change', function() {
        $(this).siblings('.custom-select-inner').text($(this).find(':selected').text());
    });

    // Feedback link
    $('.feedback').click(function(){
        MyOtziv.mo_show_box();
        return false;
    });

    //Contacts form
    $('.contacts-form').ajaxForm({
        beforeSubmit: before_submit,
        success: function(data, statusText, xhr, $form) {
            $form.find('.error').remove();
            if (data['result'] == 'success') {
                open_ok_dialog(data['response']);
                $form.resetForm();
            }
            else if (data['result'] == 'error') {
                display_form_errors(data['response'], $form);
            }
            after_submit($form);
        },
        dataType: 'json'
    });

    try {
        addthis.init();
    }
    catch(e) {
    }

    /*$('#nav #manage_shops').click(function(e){
        reachGoal('MANAGE_SHOPS');
        open_loading();
        $('#nav .current').removeClass('current');
        $(this).parent().addClass('current');
        $('#main_wrapper').load($(this).attr('href'), function() {
            $('#small_api_download_wrapper:hidden').removeClass('hidden');
            $('#api_download_wrapper:hidden').removeClass('hidden');
            $('#small_api_download_wrapper:visible').hide().addClass('hidden');
            $('#api_download_wrapper:visible').hide().addClass('hidden');
            close_loading();
        });
        update_shops_formset();
        e.preventDefault()
    });

    /*$('#nav #main').click(function(e){
        load_main_form(this);
        e.preventDefault()
    });

    if (document.location.hash=='#manage')
    {
        $('[data-hash=manage]').click();
    }

    $('a[data-hash]').live('click', function(){
        document.location.hash=$(this).attr('data-hash');
    });*/
});
