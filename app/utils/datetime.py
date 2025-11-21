# ============================================================
# app/utils/datetime.py
# Padronização central de datas e horários do projeto
# ============================================================

import pytz
from datetime import datetime, timezone, timedelta

# Timezone fixo (UTC-3 - Teresina / Fortaleza)
TZ_FORTALEZA = pytz.timezone("America/Fortaleza")

def now_local():
    """
    Retorna o horário local padronizado em UTC-3 (Teresina),
    removendo qualquer distorção do Windows.
    """
    dt = datetime.now(tz=TZ_FORTALEZA)
    return dt.replace(tzinfo=timezone(timedelta(hours=-3)))
