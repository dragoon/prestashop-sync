var maxFileSize = 10000000; // максимальный размер файла - 10 мб.

function dragdrop(selector, stateChange) {
    $(selector).live('drop', function(e) {
        e.preventDefault();
        $(this).removeClass('hover drop-error').addClass('drop');

        var files = e.originalEvent.dataTransfer.files;

        if (files[0].size > maxFileSize) {
            $(this).text($('#html_file_too_big').text());
            $(this).addClass('drop-error');
            return false;
        }
        var xhr = new XMLHttpRequest();
        xhr.upload.addEventListener('progress', uploadProgress, false);
        xhr.onload = function(event) {
            stateChange(event);
        };

        // Submit file as form
        var formData = new FormData();
        $.each(files, function(i, file) {
            uploaded_file_names[i] = file.name;
            formData.append(i, file);
        });

        xhr.open('POST', $(this).attr('data-upload-url'));
        xhr.send(formData);
    });
}
