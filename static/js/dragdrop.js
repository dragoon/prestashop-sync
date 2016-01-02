var uploaded_file_names = ['Your File'];
var currentImageName = '';

function uploadProgress(event) {
    var dropZone = $('.product-image-upload.drop-zone.drop');
    if (!dropZone.length){
        dropZone = $('.drop-zone.drop');
    }
    else {
        currentImageName = dropZone.find('div').text();
    }
    var percent = parseInt(event.loaded / event.total * 100);
    dropZone.find('div').text('Loading: ' + percent + '%');
}

function removeUpdateCSVFile() {
    var dropZone = $('#load_data_form #drop_zone');
    dropZone.siblings('.file-list').hide().empty();
    $('#id_csv_file').show().attr('required', true);
    dropZone.find('div').text($('#html5_upload_file').text());
    dropZone.removeClass('drop drop-warning');
    $.post(dropZone.attr('data-clear-url'));
    return false;
}

function removeUploadedImage() {
    var li = $(this).parent();
    var ul = li.parent();
    var dropZone = $(this).parents('ul.file-list').siblings('.drop-zone');
    var i = ul.find('li').index(li);
    li.remove();
    dropZone.height(dropZone.parent().height()-dropZone.siblings('.file-list').height()-8);
    $.post(dropZone.attr('data-clear-url'), {'i':i});
    return false;
}

$(document).ready(function() {
    $('a.csv-action.delete').live('click', removeUpdateCSVFile);
    $('a.img-action.delete').live('click', removeUploadedImage);

    if (window.FormData == null) {
        return;
    }

    $('#drop_zone').fadeIn();
    $('#drop_zone').css('display', 'table');

    $('.drop-zone').live({
        dragenter: function() {
            return false;
        },
        dragover: function() {
            $(this).addClass('hover');
            return false;
        },
        dragleave: function() {
            $(this).removeClass('hover');
            return false;
        }
    });

    dragdrop('#drop_zone', function(event) {
        var dropZone = $('.drop-zone.drop');
        var response = $.parseJSON(event.target.responseText);
        dropZone.find('div').empty().text(response['response']);
        if (event.target.status == 200) {
            dropZone.siblings('.file-list').empty();
            $('#id_csv_file').hide().removeAttr('required');
            dropZone.siblings('.file-list').append(uploaded_file_names[0]).append('<a href="#" class="csv-action delete"></a>').show();
            if (response['warning']) {
                dropZone.removeClass('drop').addClass('drop-warning');
                dropZone.find('div').append('<br><span>'+response['warning']+'</span>');
            }
        }
        else {
            dropZone.removeClass('drop').addClass('drop-error');
        }
    });

    dragdrop('#add_products_csv', function(event) {
        var dropZone = $('.drop-zone.drop');
        var response = $.parseJSON(event.target.responseText);
        dropZone.find('div').text(response['response']);
        if (event.target.status == 200) {
            var lines = response['lines'],
            fragment = document.createDocumentFragment(),
            div = $('#edit_shop_wrapper > .product-image-upload.drop-zone');

            for (var i=0;i<lines;i++) {
                var temp = div.clone(true, true);

                // Replace image url in a clone
                temp.attr('data-upload-url', temp.attr('data-upload-url').replace(/images\/0/g, 'images/'+i));
                temp.attr('data-clear-url', temp.attr('data-clear-url').replace(/images\/0/g, 'images/'+i));
                temp.find('span.product-title').text(response['names'][i]);
                fragment.appendChild(temp[0]);
            }
            $('.add-shop-products-form div.formset, .add-shop-products-form .add-more').fadeOut(function(){
                $('.add-shop-products-form .wrapper').append(fragment);
                $('.add-shop-products-form .product-image-upload.drop-zone').show().css('display', 'table');
            });
        }
        else {
            dropZone.removeClass('drop').addClass('drop-error');
            $('.product-image-upload.drop-zone').fadeOut(function() {
                $('.add-shop-products-form div.formset, .add-shop-products-form .add-more').show();
            });
        }
    });

    dragdrop('.images .drop-zone', function(event) {
        var dropZone = $('.drop-zone.drop');
        var response = $.parseJSON(event.target.responseText);
        dropZone.find('div').text(response['response']);
        if (event.target.status == 200) {
            $.each(uploaded_file_names, function(i, name){
                dropZone.siblings('.file-list').append('<li>'+name+'<a href="#" class="img-action delete"></a></li>');
                dropZone.height(dropZone.parent().height()-dropZone.siblings('.file-list').height()-8);
            });
            dropZone.removeClass('drop');
        }
        else {
            dropZone.removeClass('drop').addClass('drop-error');
        }
    });

    dragdrop('.product-image-upload.drop-zone', function(event) {
        var dropZone = $('.product-image-upload.drop-zone.drop');
        dropZone.find('div').text(currentImageName);
        if (event.target.status == 200) {
            //dropZone.removeClass('drop');
        }
        else {
            dropZone.removeClass('drop').addClass('drop-error');
        }
    })
});
