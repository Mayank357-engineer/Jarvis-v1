# ==============================
# JARVIS RUNTIME SETTINGS
# ==============================

# Brain modes
BRAIN_OFFLINE = "OFFLINE"
BRAIN_ONLINE = "ONLINE"

# Speech-to-text modes
STT_LOCAL = "LOCAL"
STT_CLOUD = "CLOUD"

# Current selections
BRAIN_MODE = BRAIN_OFFLINE
STT_MODE = STT_LOCAL
CURRENT_PERSON_CONTEXT = None


def set_brain_mode(mode):
    global BRAIN_MODE

    if mode in (BRAIN_OFFLINE, BRAIN_ONLINE):
        BRAIN_MODE = mode
        return True

    return False


def set_stt_mode(mode):
    global STT_MODE

    if mode in (STT_LOCAL, STT_CLOUD):
        STT_MODE = mode
        return True

    return False
