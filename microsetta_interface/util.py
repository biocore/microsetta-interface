import inspect
import pandas as pd

def has_non_keyword_arguments(func):
    sig = inspect.signature(func)
    params = sig.parameters
    for p in params:
        if params[p].kind != inspect.Parameter.KEYWORD_ONLY:
            return True

def parse_request_csv_col(request, file_name, col_name):
    """
    :param request: Flask request object
    :param file_name: Name of csv file in flask request
    :param col_name: Name of column to retrieve from csv file
    :return: The tuple: (column_data: list, error: Optional[string])
    """
    if file_name not in request.files or request.files[file_name].filename == '':
        return None, 'Must specify a valid file'

    request_file = request.files[file_name]
    try:
        df = pd.read_csv(request_file, dtype=str)
        col = df[col_name].tolist()
    except Exception as e:  # noqa
        return None, 'Could not parse csv file'

    return col, None
