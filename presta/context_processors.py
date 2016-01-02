from presta.forms import LoadDataForm

def show_help(request):
    """
    A context processor that sets show_help variable
    """
    return {
        'auth': not request.user.is_guest(),
    }

def csv_files(request):
    """
    A context processor for checking if csv file is in session
    """
    return {
        'update_csv_file': request.session.get(LoadDataForm.CSV_FILE_NAME)
    }
