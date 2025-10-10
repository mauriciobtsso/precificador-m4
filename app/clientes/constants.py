# ======================
# Constantes para cadastro de Armas
# ======================

TIPOS_ARMA = [
    ("revolver", "Revólver"),
    ("pistola", "Pistola"),
    ("rifle", "Rifle"),
    ("espingarda", "Espingarda"),
    ("carabina_fuzil", "Carabina / Fuzil"),
    ("garruncha", "Garruncha"),
    ("outros", "Outros"),
]

FUNCIONAMENTO_ARMA = [
    ("repeticao", "Repetição"),
    ("semi_automatica", "Semi-automática"),
    ("automatica", "Automática"),
    ("outros", "Outros"),
]

EMISSORES_CRAF = [
    ("sigma", "Sigma"),
    ("sinarm", "Sinarm"),
    ("sinarm_cac", "Sinarm-CAC"),
]

CATEGORIAS_ADQUIRENTE = [
    ("civil", "Civil (cidadão comum)"),
    ("atirador", "Atiradores"),
    ("colecionador", "Colecionador"),
    ("cac_excepcional", "Caçador Excepcional (CAC)"),
    ("cac_subsistencia", "Caçador de Subsistência"),
    ("policial_militar", "Policial Militar"),
    ("guarda_municipal", "Guarda Municipal"),
    ("instrutor_pf", "Instrutor Polícia Federal"),
    ("abin", "Agente da ABIN"),
    ("gsi", "Agente do Dep. Seg. do GSI da PR"),
    ("analista_tributario", "Analista Tributário"),
    ("auditor_fiscal", "Auditor-Fiscal"),
    ("bombeiro_militar", "Bombeiro Militar"),
    ("guarda_portuario", "Guarda Portuário"),
    ("loja", "Loja"),
    ("magistrado", "Magistrado"),
    ("ministerio_publico", "Membro do Ministério Público"),
    ("militar_forcas_armadas", "Militar das Forças Armadas"),
    ("policial_civil", "Policial Civil"),
    ("policial_camara", "Policial da Câmara dos Deputados"),
    ("policial_senado", "Policial do Senado Federal"),
    ("policial_federal", "Policial Federal"),
    ("policial_rodoviario", "Policial Rodoviário Federal"),
]


# Categorias exibidas no formulário e usadas pelo OCR/validação
CATEGORIAS_DOCUMENTO = [
    ("CR", "Certificado de Registro (CR)"),
    ("CRAF", "Certificado de Registro de Arma de Fogo (CRAF)"),
    ("RG", "Registro Geral (RG)"),
    ("CPF", "Cadastro de Pessoa Física (CPF)"),
    ("CNH", "Carteira Nacional de Habilitação (CNH)"),
    ("COMPROVANTE_RESIDENCIA", "Comprovante de Residência"),
    ("NOTA_FISCAL", "Nota Fiscal"),
    ("OUTRO", "Outro"),
]

# Órgãos emissores comuns (usados em selects e no parser do OCR)
EMISSORES_DOCUMENTO = [
    "SINARM",
    "SIGMA",
    "SSP",
    "DETRAN",
    "RECEITA FEDERAL",
    "JUSTIÇA FEDERAL",
    "OUTRO",
]

