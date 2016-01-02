$(document).ready(function() {
    /*$('#auth_panel').mouseleave(function (){
        $(this).animate({top:-43}, 500);
    }).mouseenter(function (){
        $(this).animate({top:0}, 300);
    });*/
    $('#register_form').live('submit', function() {
        $('#facebox #register_form').ajaxSubmit({
            beforeSubmit: before_submit,
            success: function(data, statusText, xhr, $form) {
                $form.find('.error').remove();
                if (data['result'] == 'success') {
                    open_ok_dialog(data['response']);
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

    $('#login_form').live('submit', function() {
        $('#facebox #login_form').ajaxSubmit({
            beforeSubmit: before_submit,
            success: function(data, statusText, xhr, $form) {
                $form.find('.error').remove();
                if (data['result'] == 'success') {
                    window.location = data['response'];
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

    $('#full_login_form').ajaxForm({
        beforeSubmit:before_submit,
        success:function (data, statusText, xhr, $form) {
            $form.find('.error').remove();
            if (data['result'] == 'success') {
                window.location = data['response'];
            }
            else if (data['result'] == 'error') {
                display_form_errors(data['response'], $form);
            }
            after_submit($form);
        },
        dataType:'json'
    });
});
