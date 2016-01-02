$(document).ready(function() {

    var start_date = $('form.payment.business span.start-date').text().split('.').reverse();
    start_date = new Date(start_date[0],parseInt(start_date[1])-1, start_date[2]);

    $('select.plan-select').live('change', function() {
        $('form.payment').toggle();
    });

    $('form.payment.business input.main').live('input', function() {
        var $form = $(this).parents('form');
        var amount = $(this).val();
        if (!parseInt(amount) || parseInt(amount)<3) {
            amount = "3";
        }
        var days = parseInt(amount) * 2;
        if (days>36) {
            days += Math.floor(days/31) * 7;
        }
        var end_date = new Date(start_date.getFullYear(), start_date.getMonth(), start_date.getDate() + days);
        $form.find('span.end-date').text(end_date.getDate()+"."+('0'+(end_date.getMonth()+1)).slice(-2)+"."+end_date.getFullYear());;
        $form.find('input[name="amount"]').val(amount);
    });

    $('form.payment.business-small input.main').live('input', function() {
        var $form = $(this).parents('form');
        var amount = $(this).val();
        if (!parseInt(amount) || parseInt(amount)<3) {
            amount = "3";
        }
        var days = parseInt(amount) * 6;
        var end_date = new Date(start_date.getFullYear(), start_date.getMonth(), start_date.getDate() + days);
        $form.find('span.end-date').text(end_date.getDate()+"."+('0'+(end_date.getMonth()+1)).slice(-2)+"."+end_date.getFullYear());;
        $form.find('input[name="amount"]').val(amount);
    });
});
