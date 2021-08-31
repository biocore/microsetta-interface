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

def parse_request_csv(request, file_name, required_cols):
    """
    :param request: Flask request object
    :param file_name: Name of csv file in flask request
    :param required_cols: Columns that must be in CSV header
    :return: The tuple: (csv_data: dict, error: Optional[string])
    """
    if file_name not in request.files or request.files[file_name].filename == '':
        return None, 'Must specify a valid file'

    request_file = request.files[file_name]
    try:
        df = pd.read_csv(request_file, dtype=str,keep_default_na=False)

        missing_cols = []

        for col_name in required_cols:
            if col_name not in df.columns:
                missing_cols.append(col_name)

        if len(missing_cols) > 0:
            missing_cols_str = ",".join(missing_cols)
            return None, 'CSV file missing columns: ' + missing_cols_str
        else:
            csv_contents = df.to_dict('index')
    except Exception as e:  # noqa
        return None, 'Could not parse csv file'

    return csv_contents, None

def dict_to_csv(dict_convert):
    """
    :param dict_convert: The dictionary to write to a CSV
    :param cols_write: List of columns to write
    :return: String to write to file
    """
    df = pd.DataFrame.from_dict(dict_convert,orient='index')
    csv_str = df.to_csv(index=False)
    return csv_str
