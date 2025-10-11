// static/js/armas.js (VERSÃO FINAL E CORRIGIDA POR MANUS)

document.addEventListener('DOMContentLoaded', function () {
    // Função para exibir feedback de carregamento (spinner)
    function showLoading(button, text = 'Processando...') {
        if (!button) return;
        button.originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ${text}`;
    }

    // Função para restaurar o estado original do botão
    function hideLoading(button) {
        if (!button || !button.originalText) return;
        button.disabled = false;
        button.innerHTML = button.originalText;
    }

    // Função para preencher os campos do formulário de nova arma com os dados do OCR
    function preencherFormularioNovaArma(data) {
        const fieldMapping = {
            tipo: 'formNovaArma_tipo',
            funcionamento: 'formNovaArma_funcionamento',
            marca: 'formNovaArma_marca',
            modelo: 'formNovaArma_modelo',
            calibre: 'formNovaArma_calibre',
            numero_serie: 'formNovaArma_numero_serie',
            emissor_craf: 'formNovaArma_emissor_craf',
            numero_sigma: 'formNovaArma_numero_sigma',
            categoria_adquirente: 'formNovaArma_categoria_adquirente',
            caminho_craf: 'formNovaArma_caminho_craf'
        };

        for (const key in data) {
            if (fieldMapping[key]) {
                const field = document.getElementById(fieldMapping[key]);
                if (field) {
                    if (field.tagName === 'SELECT') {
                        let optionFound = false;
                        for (let option of field.options) {
                            if (option.value.toLowerCase() === String(data[key]).toLowerCase() || option.text.toLowerCase() === String(data[key]).toLowerCase()) {
                                field.value = option.value;
                                optionFound = true;
                                break;
                            }
                        }
                    } else {
                        field.value = data[key];
                    }
                }
            }
        }

        // ==================================================================
        // AQUI ESTÁ A CORREÇÃO PARA A DATA DE VALIDADE
        // ==================================================================
        const dataValidadeField = document.getElementById('formNovaArma_data_validade_craf');
        if (dataValidadeField && data.data_validade_craf) {
            const dateString = data.data_validade_craf;
            // Verifica se a data está no formato DD/MM/YYYY
            if (dateString.includes('/')) {
                const parts = dateString.split('/');
                if (parts.length === 3) {
                    const [day, month, year] = parts;
                    // Formata para YYYY-MM-DD, que é o formato que o input[type=date] aceita
                    dataValidadeField.value = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
                }
            } else {
                // Se já estiver no formato YYYY-MM-DD, apenas atribui
                dataValidadeField.value = dateString;
            }
        }

        const validadeIndetCheckbox = document.getElementById('formNovaArma_validade_indeterminada');
        if (validadeIndetCheckbox) {
            validadeIndetCheckbox.checked = data.validade_indeterminada || false;
        }
    }

    // --- Lógica principal para o formulário de NOVA ARMA ---
    const btnProcessarOcr = document.getElementById('btnProcessarOcr');
    const uploadInput = document.getElementById('uploadNovaArma');
    
    // Função que executa o OCR
    const executarOcr = () => {
        const file = uploadInput.files[0];
        if (!file) {
            // Não faz nada se nenhum arquivo for selecionado (ex: clicar em cancelar)
            return;
        }

        const clienteIdElement = document.querySelector('[data-bs-target="#modalNovaArma"]');
        const clienteId = clienteIdElement ? clienteIdElement.dataset.clienteId : null;

        if (!clienteId) {
             alert('Erro crítico: ID do cliente não encontrado. Não foi possível processar o OCR.');
             return;
        }

        showLoading(btnProcessarOcr);

        const formData = new FormData();
        formData.append('file', file);

        fetch(`/uploads/${clienteId}/craf`, {
            method: 'POST',
            body: formData,
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Erro no servidor: ${response.statusText} (Status: ${response.status})`);
            }
            return response.json();
        })
        .then(data => {
            hideLoading(btnProcessarOcr);
            if (data.error) {
                alert('Erro ao ler o documento: ' + data.error);
            } else {
                const dadosNormalizados = normalizeDados(data);
                preencherFormularioNovaArma(dadosNormalizados);
                // Opcional: pode remover o alert para uma experiência mais fluida
                // alert('Campos preenchidos pelo OCR! Por favor, verifique os dados e salve a arma.');
            }
        })
        .catch(error => {
            hideLoading(btnProcessarOcr);
            console.error('Erro ao processar OCR:', error);
            alert('Ocorreu um erro de comunicação ao processar o arquivo. Verifique o console para mais detalhes.');
        });
    };

    if (uploadInput) {
        // ==================================================================
        // AQUI ESTÁ A CORREÇÃO PARA O PROCESSAMENTO AUTOMÁTICO
        // ==================================================================
        // O evento 'change' é disparado assim que um arquivo é selecionado.
        uploadInput.addEventListener('change', executarOcr);
    }

    if (btnProcessarOcr) {
        // O botão de clique agora serve como um backup, caso o usuário queira reenviar.
        btnProcessarOcr.addEventListener('click', executarOcr);
    }

    // Sua lógica original de normalização de dados (mantida intacta)
    function normalizeDados(json) {
        const d = json || {};
        let serie = (d.numero_serie || "").toString().trim();
        let modelo = (d.modelo || "").toString().trim();
        let calibre = (d.calibre || "").toString().trim();
        let marca = (d.marca || "").toString().trim();
        const separadorSerie = /Nº Da Arma:/i;
        if (separadorSerie.test(modelo)) {
            const partes = modelo.split(separadorSerie);
            modelo = partes[0].trim();
            if (partes[1].trim()) serie = partes[1].trim();
        }
        const separadorCapacidade = /Capacidade de Tiros/i;
        if (separadorCapacidade.test(calibre)) {
            calibre = calibre.split(separadorCapacidade)[0].trim();
        }
        const tiposDeArma = ["PISTOLA", "REVÓLVER", "REVOLVER", "ESPINGARDA", "CARABINA", "FUZIL"];
        for (const tipo of tiposDeArma) {
            const regex = new RegExp(`^${tipo}\\s+`, "i");
            if (regex.test(marca)) {
                marca = marca.replace(regex, "").trim();
                break;
            }
        }
        const marcaUpper = marca.toUpperCase();
        if (marcaUpper.includes("FORJAS TAURUS") || marcaUpper.includes("TAURUS ARMAS")) marca = "TAURUS";
        else if (marcaUpper.includes("COMPANHIA BRASILEIRA DE CARTUCHOS")) marca = "CBC";
        const calibreUpper = calibre.toUpperCase();
        if (calibreUpper.includes("9X19") || calibreUpper.includes("9MM") || calibreUpper.includes("9 MM")) calibre = "9x19";
        let sigmaFinal = "";
        let candidatoSigma = (d.numero_sigma || d.numero_documento || "").toString().trim();
        if (serie && candidatoSigma.includes(serie)) candidatoSigma = candidatoSigma.replace(serie, "").trim();
        const onlyDigits = (str) => (str || "").replace(/\D+/g, "");
        const sigmaLimpo = onlyDigits(candidatoSigma);
        if (sigmaLimpo && sigmaLimpo !== onlyDigits(serie)) sigmaFinal = sigmaLimpo;
        else if (onlyDigits(d.numero_sigma) && onlyDigits(d.numero_sigma) !== onlyDigits(serie)) sigmaFinal = onlyDigits(d.numero_sigma);
        let tipoInferido = d.tipo || "";
        if (!tipoInferido) {
            const textoCompleto = `${d.marca || ""} ${modelo} ${d.tipo || ""}`.toUpperCase();
            if (textoCompleto.includes("PISTOLA")) tipoInferido = "Pistola";
            else if (textoCompleto.includes("REVÓLVER") || textoCompleto.includes("REVOLVER")) tipoInferido = "Revólver";
            else if (textoCompleto.includes("ESPINGARDA")) tipoInferido = "Espingarda";
            else if (textoCompleto.includes("CARABINA") || textoCompleto.includes("FUZIL")) tipoInferido = "Carabina";
        }
        let funcInferido = d.funcionamento || "";
        if (!funcInferido) {
            const tipoLower = tipoInferido.toLowerCase();
            if (tipoLower === "pistola") funcInferido = "Semi-automática";
            else if (tipoLower === "revólver") funcInferido = "Repetição";
        }
        const mapEmissor = (e) => {
            const t = (e || "").toUpperCase();
            if (t.includes("EXÉRCITO") || t.includes("MILITAR") || t.includes("BOMBEIROS")) return "sigma";
            if (t.includes("FEDERAL") || t.includes("JUSTIÇA")) return "sinarm";
            return (e || "").toLowerCase();
        };
        return {
            tipo: tipoInferido,
            funcionamento: funcInferido,
            marca: marca.toUpperCase(),
            modelo: modelo.toUpperCase(),
            calibre: calibre.toUpperCase(),
            numero_serie: serie.toUpperCase(),
            numero_sigma: sigmaFinal,
            emissor_craf: mapEmissor(d.emissor_craf || d.emissor),
            categoria_adquirente: (d.categoria_adquirente || "").toUpperCase(),
            data_validade_craf: d.data_validade_craf || d.data_validade || "",
            validade_indeterminada: !!d.validade_indeterminada,
            caminho_craf: d.caminho_craf || d.caminho || "",
            nome_original: d.nome_original || d.nome || ""
        };
    }
});
