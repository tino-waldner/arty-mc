import os
import stat


def is_accessible(path) -> bool:
    try:
        if os.path.islink(path) and not os.path.exists(path):
            return False

        real_path = os.path.realpath(path)
        st = os.stat(real_path)
        mode = st.st_mode

        if stat.S_ISDIR(mode):
            return os.access(real_path, os.R_OK) and os.access(real_path, os.X_OK)
        elif stat.S_ISREG(mode):
            return os.access(real_path, os.R_OK)
        else:
            return False
    except Exception:
        return False


def is_copyable(path) -> bool:

    if not is_accessible(path):
        return False

    if os.path.isdir(path):
        try:
            return len(os.listdir(path)) > 0
        except Exception:
            return False

    return True
