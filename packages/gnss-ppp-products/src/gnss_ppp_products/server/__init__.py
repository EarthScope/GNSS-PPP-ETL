from .ftp import ftp_list_directory, ftp_download_file, ftp_find_best_match_in_listing
from .http import extract_filenames_from_html, http_list_directory

try:
    from .products import process_product_query
    from .antennae import process_antennae_query
except ImportError:
    pass