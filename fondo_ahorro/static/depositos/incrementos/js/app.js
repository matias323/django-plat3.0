/**
 * LÓGICA DE TEMPLATE DE INCREMENTO DE AHORRO
 *
 */
//capturar el crftoken para las solicitudes
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
document.addEventListener('DOMContentLoaded', () => {
    let timerBusquedaPartner = null;
    const inputBuscarPartner = document.getElementById('input-search-persona');
    const resultSearchPartner = document.getElementById('dropdown-search-results');
    const btnClearSearch = document.getElementById('btn-clear-search');
    const inputMonto = document.getElementById('input-monto-incremento');
    const btnLimpiarMonto = document.getElementById('btn-limpiar-monto');
    let dataResult = [];
    
    const ahorrosState = {
        selectedPerson: [],
        selectedAccount: null, // Cuenta de ahorro activa seleccionada entre las 3 disponibles
        incrementAmount: 0,
        attachedFiles: [],
    };

    /**
     * Formatear monto a CLP
     */
    function formatMoney(amount) {
        const num = parseInt(amount) || 0;
        return num.toLocaleString('es-CL', { 
            style: 'currency',
            currency: 'CLP',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0 });
    }

    /**
     * Formatear RUT Chileno con puntos y guión
     * Ejemplo: 154829147 -> 15.482.914-7
     */
    function formatRUT(rutStr) {
        if (!rutStr) return '';
        let clean = rutStr.replace(/[^0-9kK]/g, '').toUpperCase();
        if (clean.length < 2) return clean;
        let cuerpo = clean.slice(0, -1);
        let dv = clean.slice(-1);
        return cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + '-' + dv;
    }

    /**
     * Formatear bytes a tamaño legible (KB / MB)
     */
    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    const initBuscador = () => {
        inputBuscarPartner.addEventListener('input', () => {
            clearTimeout(timerBusquedaPartner);

            const search = inputBuscarPartner.value.trim();
            resultSearchPartner.innerHTML = '';

            if (btnClearSearch) {
                btnClearSearch.classList.toggle('d-none', search.length === 0);
            }

            if(search.length <2) {
                resultSearchPartner.classList.remove('show');
                resultSearchPartner.innerHTML = '';
                return;
            }

            timerBusquedaPartner = setTimeout(() => {
                buscarPartner(search)
            }, 300)
        })

        inputBuscarPartner.addEventListener('focus', () => {
            const search = inputBuscarPartner.value.trim().toLowerCase();
            if (search.length >= 1) {
                const resultados = buscarPartner(search);
                // renderizarDropdownResultados(resultados, query);
            }
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.live-search-container')) {
                resultSearchPartner.classList.remove('show');
            }
        });

        if (btnClearSearch) {
            btnClearSearch.addEventListener('click', () => {
                inputBuscarPartner.value = '';
                resultSearchPartner.classList.remove('show');
                btnClearSearch.classList.add('d-none');
                inputBuscarPartner.focus();
            });
        }


    }

    initBuscador();

    //realizar peticion de busqueda
    const buscarPartner = async (search) => {
        try{
            resultSearchPartner.innerHTML = `
            <div class="list-group-item text-muted>
                Buscando...
            </div>`

            const response = await fetch(`/depositos/busqueda-partner/?q=${encodeURIComponent(search)}`, 
            {
                method: 'GET',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                }
            });

            if(!response.ok){
                throw new Error('Respuesta inválida del servidor')
            }

            const data = await response.json()
            dataResult = data.data
            // return
            if(!data.success) {
                throw new Error(data.message || 'No es posible obtener los auxiliares')
            }

            renderizarDropdownResultados(data.data)
        } catch (error){
            console.error(error)
            resultSearchPartner.innerHTML = `
            <div class="list-group-item text-danger>
                ${error.message || 'No es posible obtener los auxiliares'}
            </div>`
        }
    }

    function renderizarDropdownResultados(resultados) {
        const dropdown = document.getElementById('dropdown-search-results');
        if (!dropdown) return;

        if (resultados.length === 0) {
            dropdown.innerHTML = `
                <div class="p-3 text-center text-muted">
                    <i class="bi bi-person-x fs-4 d-block mb-1"></i>
                    <span class="small">No se encontraron socios que coincidan con la busqueda"</span>
                </div>
            `;
            dropdown.classList.add('show');
            return;
        }

        let html = '';
        resultados.forEach(p => {
            const ahorros = p.ahorros || [];
            const totalConsolidado = ahorros.reduce((acc, c) => acc + (Number(c.amount) || 0), 0);
            const saldoConsolidadoCLP = formatMoney(totalConsolidado);

            html += `
            <div class="search-result-item" data-socio-id="${p.id_partner}">
                <div class="flex-grow-1 overflow-hidden">
                    <div class="d-flex align-items-center justify-content-between">
                        <strong class="text-dark fs-sm text-truncate">${p.nombre}</strong>
                        <span class="badge bg-success-subtle text-success border border-success-subtle ms-2 cell-currency-clp">
                            Total Ahorros: ${saldoConsolidadoCLP}
                        </span>
                    </div>
                    <div class="d-flex align-items-center gap-2 small text-muted mt-0">
                        <span class="badge bg-light text-secondary border font-monospace fs-xs">RUT: ${formatRUT(p.rut)}</span>
                        <span class="badge bg-light text-secondary border font-monospace fs-xs">CODIGO FUNCIONARIO: ${p.codigo_funcionario}</span>
                        <span class="badge bg-light text-secondary border font-monospace fs-xs">GRADO: ${p.grado}</span>
                        <span>•</span>
                        <span class="fs-xs text-truncate text-primary fw-semibold">
                            <i class="bi bi-wallet2 me-1"></i>${p.ahorros.length} cuentas de ahorro
                        </span>
                    </div>
                </div>
            </div>
            `;
        });

        dropdown.innerHTML = html;
        dropdown.classList.add('show');

        // Asignar clic a cada ítem de resultado
        dropdown.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', () => {
                const socioId = item.dataset.socioId;
                const socio = dataResult.find(p => p.id_partner == socioId);
                if (socio) {
                    seleccionarPersona(socio);
                    dropdown.classList.remove('show');
                    dropdown.innerHTML = '';
                }
            });
        });
    }

    function seleccionarPersona(persona) {
        ahorrosState.selectedPerson = persona;

        // Actualizar input de búsqueda
        const inputSearch = document.getElementById('input-search-persona');
        if (inputSearch) {
            inputSearch.value = `${persona.nombre} (${persona.rut})`;
        }

        // Mostrar sección de información personal, selector de cuentas y formulario
        const sectionProfile = document.getElementById('seccion-perfil-socio');
        const sectionCuentas = document.getElementById('seccion-seleccion-cuentas');
        const placeholderSelect = document.getElementById('placeholder-no-socio');
        const formIncremento = document.getElementById('seccion-formulario-incremento');

        if (sectionProfile) sectionProfile.classList.remove('d-none');
        if (sectionCuentas) sectionCuentas.classList.remove('d-none');
        if (placeholderSelect) placeholderSelect.classList.add('d-none');
        if (formIncremento) formIncremento.classList.remove('opacity-50', 'pointer-events-none');

        // Llenar datos personales
        // document.getElementById('perfil-avatar').src = persona.avatar;
        document.getElementById('perfil-nombre').textContent = persona.nombre;
        document.getElementById('perfil-rut').textContent = formatRUT(persona.rut);
        document.getElementById('perfil-id-socio').textContent = persona.codigo_funcionario;
        document.getElementById('perfil-categoria').textContent = persona.categoria;
        document.getElementById('perfil-grado').textContent = persona.grado;
        document.getElementById('perfil-escalafon').textContent = persona.grado_escalafon;
        // document.getElementById('perfil-direccion').textContent = persona.direccion;
        // document.getElementById('perfil-comuna').textContent = persona.comuna;
        // document.getElementById('perfil-fecha-afiliacion').textContent = persona.fecha_socio;

        // Renderizar las 3 tarjetas de ahorro y preseleccionar la primera
        const cuentas = persona.ahorros || [];
        renderizarCuentasSocio(persona);

        if (cuentas.length > 0) {
            seleccionarCuentaAhorro(cuentas[0], false);
        }

        // Enfocar el input de monto de incremento
        setTimeout(() => {
            const inputMonto = document.getElementById('input-monto-incremento');
            if (inputMonto) {
                inputMonto.focus();
                inputMonto.select();
            }
        }, 150);
    }

    function renderizarCuentasSocio(persona) {
        const contenedor = document.getElementById('contenedor-cuentas-socio');
        const selectDestino = document.getElementById('select-cuenta-destino');
        const elConsolidado = document.getElementById('saldo-total-consolidado-socio');

        if (!contenedor || !persona || !persona.ahorros) return;

        const cuentas = persona.ahorros;
        const totalConsolidado = cuentas.reduce((acc, c) => acc + (Number(c.amount) || 0), 0);

        if (elConsolidado) {
            elConsolidado.textContent = formatMoney(totalConsolidado);
        }

        // 1. Renderizar tarjetas de las 3 cuentas
        let htmlCards = '';
        cuentas.forEach((c) => {
            const isSelected = ahorrosState.selectedAccount && ahorrosState.selectedAccount.idCuenta == c.contribution_type_id;
            const iconClass = c.icono || 'bi-wallet2';
            const color = c.badgeColor || 'primary';

            htmlCards += `
            <div class="col-12 col-md-4">
                <div class="account-select-card ${isSelected ? 'selected' : ''}" data-cuenta-id="${c.contribution_type_id}">
                    <div class="d-flex align-items-center justify-content-between mb-2">
                        <div class="d-flex align-items-center gap-2">
                            <div class="account-card-icon bg-${color}-subtle text-${color}">
                                <i class="bi ${iconClass}"></i>
                            </div>
                            <div>
                                <span class="badge bg-${color}-subtle text-${color} border border-${color}-subtle fs-xs">
                                    ${c.description}
                                </span>
                            </div>
                        </div>
                        <div class="account-radio-circle">
                            <i class="bi bi-check-lg ${isSelected ? '' : 'd-none'}"></i>
                        </div>
                    </div>

                    <div class="mb-2">
                        <h6 class="fw-bold mb-1 text-dark fs-sm">${c.description} - ${c.comment}</h6>
                        <span class="badge bg-light text-secondary border font-monospace fs-xs">
                            <i class="bi bi-hash"></i> ${c.description}
                        </span>
                    </div>

                    <div class="pt-2 border-top d-flex justify-content-between align-items-end mt-auto">
                        <div>
                            <span class="text-muted fs-xs d-block">Saldo Actual:</span>
                            <span class="account-balance-tag">${formatMoney(c.amount)}</span>
                        </div>
                    </div>
                </div>
            </div>
            `;
        });

        contenedor.innerHTML = htmlCards;

        // Escuchador de clic en cada tarjeta
        contenedor.querySelectorAll('.account-select-card').forEach(card => {
            card.addEventListener('click', () => {
                const cuentaId = card.dataset.cuentaId;
                const cuenta = cuentas.find(c => c.contribution_type_id == cuentaId);
                if (cuenta) {
                    seleccionarCuentaAhorro(cuenta, true);
                }
            });
        });

        // 2. Sincronizar select en el formulario
        if (selectDestino) {
            selectDestino.innerHTML = cuentas.map(c => `
                <option value="${c.contribution_type_id}">
                    ${c.description} - ${c.comment} (Saldo: ${formatMoney(c.amount)})
                </option>
            `).join('');

            selectDestino.onchange = (e) => {
                const chosenId = e.target.value;
                const cuenta = cuentas.find(c => c.contribution_type_id == chosenId);
                if (cuenta) {
                    seleccionarCuentaAhorro(cuenta, true);
                }
            };
        }
    }

    function seleccionarCuentaAhorro(cuenta, shouldFocusMonto = true) {
        if (!cuenta) return;

        ahorrosState.selectedAccount = cuenta;

        // 1. Actualizar estado visual de las tarjetas en la UI
        document.querySelectorAll('.account-select-card').forEach(card => {
            const isCurrent = card.dataset.cuentaId == cuenta.contribution_type_id;
            card.classList.toggle('selected', isCurrent);
            const checkIcon = card.querySelector('.account-radio-circle i');
            if (checkIcon) {
                checkIcon.classList.toggle('d-none', !isCurrent);
            }
        });

        // 2. Sincronizar select del formulario y campo oculto
        const selectDestino = document.getElementById('select-cuenta-destino');
        if (selectDestino && selectDestino.value !== cuenta.contribution_type_id) {
            selectDestino.value = cuenta.contribution_type_id;
        }

        const inputHidden = document.getElementById('input-cuenta-seleccionada-id');
        if (inputHidden) {
            inputHidden.value = cuenta.contribution_type_id;
        }

        // 3. Actualizar la Ficha Financiera Hero Box (Columna 5)
        const saldoActualCLP = formatMoney(cuenta.amount);
        document.getElementById('cuenta-saldo-actual-hero').textContent = saldoActualCLP;
        document.getElementById('proyeccion-saldo-actual').textContent = saldoActualCLP;
        document.getElementById('cuenta-numero').textContent = cuenta.description;
        document.getElementById('cuenta-tipo').textContent = `${cuenta.description} (${cuenta.comment || ''})`;
        // document.getElementById('cuenta-tasa').textContent = cuenta.tasaInteresAnual;

        // 4. Renderizar movimientos recientes exclusivos de esta cuenta
        // renderizarMovimientosRecientesCuenta(cuenta);

        // 5. Recalcular simulación y proyección de nuevo saldo
        recalcularProyeccionNuevoSaldo();

        // 6. Foco en el monto si fue activado por el usuario
        if (shouldFocusMonto) {
            const inputMonto = document.getElementById('input-monto-incremento');
            if (inputMonto) {
                inputMonto.focus();
                inputMonto.select();
            }
        }
    }

    // Validación y formateo en tiempo real al tipear: SOLO ENTEROS EN CLP
    inputMonto.addEventListener('input', (e) => {
        // 1. Eliminar cualquier caracter que no sea dígito
        let rawDigits = e.target.value.replace(/\D/g, '');

        if (!rawDigits || rawDigits === '0') {
            ahorrosState.incrementAmount = 0;
            e.target.value = '';
            recalcularProyeccionNuevoSaldo();
            return;
        }

        // 2. Parsear estrictamente como número entero
        let intVal = parseInt(rawDigits, 10);
        if (isNaN(intVal)) intVal = 0;

        ahorrosState.incrementAmount = intVal;

        // 3. Formatear visualmente con separadores de miles chilenos (puntos)
        e.target.value = intVal.toLocaleString('es-CL', {
            maximumFractionDigits: 0
        });

        // 4. Actualizar simulación de nuevo saldo
        recalcularProyeccionNuevoSaldo();
    });

    // Botón para limpiar monto
    if (btnLimpiarMonto) {
        btnLimpiarMonto.addEventListener('click', () => {
            ahorrosState.incrementAmount = 0;
            inputMonto.value = '';
            recalcularProyeccionNuevoSaldo();
            inputMonto.focus();
        });
    }

    /**
     * Recalcula la proyección del nuevo saldo para la cuenta seleccionada:
     * Saldo Anterior de la Cuenta + Monto Incremento = Nuevo Saldo de la Cuenta
     */
    function recalcularProyeccionNuevoSaldo() {
        const elIncremento = document.getElementById('proyeccion-monto-incremento');
        const elNuevoSaldo = document.getElementById('proyeccion-nuevo-saldo');

        const monto = Math.round(ahorrosState.incrementAmount || 0);

        if (elIncremento) {
            elIncremento.textContent = '+' + formatMoney(monto);
        }

        if (!ahorrosState.selectedAccount) {
            if (elNuevoSaldo) elNuevoSaldo.textContent = "$ 0";
            return;
        }

        const saldoActual = Math.round(Number(ahorrosState.selectedAccount.amount) || 0);
        const nuevoSaldo = saldoActual + monto;

        if (elNuevoSaldo) {
            elNuevoSaldo.textContent = formatMoney(nuevoSaldo);
        }
    }

    /**
     * =========================================================================
     * 4. GESTOR DE ADJUNCIÓN DE DOCUMENTOS (DRAG & DROP Y FILE SELECTOR)
     * =========================================================================
     */
    function configurarSubidaArchivos() {
        const dropzone = document.getElementById('dropzone-area');
        const fileInput = document.getElementById('input-file-doc');

        if (!dropzone || !fileInput) return;

        // Clic en dropzone abre el selector
        dropzone.addEventListener('click', () => {
            fileInput.click();
        });

        // Drag & Drop
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove('dragover');
            });
        });

        dropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            procesarArchivosSeleccionados(files);
        });

        fileInput.addEventListener('change', (e) => {
            procesarArchivosSeleccionados(e.target.files);
            fileInput.value = ''; // Reset para permitir subir el mismo archivo si se desea
        });
    }

    configurarSubidaArchivos();

    /**
     * Lee los archivos mediante FileReader y los agrega al estado
     */
    function procesarArchivosSeleccionados(fileList) {
        if (!fileList || fileList.length === 0) return;

        Array.from(fileList).forEach(file => {
            // Validar tamaño máximo: 10MB
            if (file.size > 10 * 1024 * 1024) {
                alert(`El archivo "${file.name}" supera el tamaño máximo permitido de 10 MB.`);
                return;
            }

            const isPdf = file.type === 'application/pdf';
            const isImage = file.type.startsWith('image/');

            const reader = new FileReader();
            reader.onload = (e) => {
                const fileItem = {
                    id: 'FILE-' + Date.now() + '-' + Math.floor(Math.random() * 1000),
                    name: file.name,
                    sizeBytes: file.size,
                    sizeFormatted: formatBytes(file.size),
                    type: file.type || 'application/octet-stream',
                    isPdf: isPdf,
                    isImage: isImage,
                    dataUrl: e.target.result,
                    uploadTime: new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })
                };

                ahorrosState.attachedFiles.push(fileItem);
                renderizarListaArchivosAdjuntos();
            };

            reader.readAsDataURL(file);
        });
    }

    /**
     * Renderiza las tarjetas de documentos adjuntos
     */
    function renderizarListaArchivosAdjuntos() {
        const container = document.getElementById('container-attached-files');
        const badgeCount = document.getElementById('badge-count-adjuntos');
        if (!container) return;

        if (badgeCount) {
            badgeCount.textContent = ahorrosState.attachedFiles.length;
            badgeCount.classList.toggle('d-none', ahorrosState.attachedFiles.length === 0);
        }

        if (ahorrosState.attachedFiles.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted small py-2">
                    <i class="bi bi-paperclip me-1"></i> No se han adjuntado comprobantes aún
                </div>
            `;
            return;
        }

        let html = '';
        ahorrosState.attachedFiles.forEach(f => {
            let previewThumbnail = '';
            if (f.isImage) {
                previewThumbnail = `<img src="${f.dataUrl}" alt="${f.name}" class="attached-thumbnail">`;
            } else if (f.isPdf) {
                previewThumbnail = `
                    <div class="attached-file-icon bg-danger-subtle text-danger">
                        <i class="bi bi-file-earmark-pdf-fill"></i>
                    </div>
                `;
            } else {
                previewThumbnail = `
                    <div class="attached-file-icon bg-secondary-subtle text-secondary">
                        <i class="bi bi-file-earmark-text"></i>
                    </div>
                `;
            }

            html += `
            <div class="attached-file-card mb-2" id="card-${f.id}">
                <div class="d-flex align-items-center gap-2 overflow-hidden">
                    ${previewThumbnail}
                    <div class="overflow-hidden">
                        <div class="text-dark fw-semibold fs-sm text-truncate" title="${f.name}">${f.name}</div>
                        <span class="text-muted fs-xs">${f.sizeFormatted} • Subido ${f.uploadTime}</span>
                    </div>
                </div>
                <div class="d-flex align-items-center gap-1 flex-shrink-0">
                    <button type="button" class="btn btn-outline-danger btn-sm py-1 px-2 btn-delete-file" data-file-id="${f.id}" title="Eliminar">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
            `;
        });

        container.innerHTML = html;

        // Escuchadores de previsualizar y eliminar
        // container.querySelectorAll('.btn-preview-file').forEach(btn => {
        //     btn.addEventListener('click', () => {
        //         const fileId = btn.dataset.fileId;
        //         const file = ahorrosState.attachedFiles.find(f => f.id === fileId);
        //         //abrir nueva pestaña con el archivo
        //         window.open(file.dataUrl, '_blank');
        //         if (file) abrirModalPrevisualizacion(file);
        //     });
        // });

        container.querySelectorAll('.btn-delete-file').forEach(btn => {
            btn.addEventListener('click', () => {
                const fileId = btn.dataset.fileId;
                ahorrosState.attachedFiles = ahorrosState.attachedFiles.filter(f => f.id !== fileId);
                renderizarListaArchivosAdjuntos();
            });
        });
    }

    /**
     * Modal de previsualización de archivo
     */
    // function abrirModalPrevisualizacion(file) {
    //     const modalEl = document.getElementById('modal-preview-doc');
    //     const modalTitle = document.getElementById('modal-preview-title');
    //     const modalBody = document.getElementById('modal-preview-body');

    //     if (!modalEl || !modalBody) return;

    //     modalTitle.textContent = file.name;

    //     if (file.isImage) {
    //         modalBody.innerHTML = `
    //             <div class="text-center">
    //                 <img src="${file.dataUrl}" alt="${file.name}" class="img-fluid rounded border shadow-sm" style="max-height: 70vh;">
    //             </div>
    //         `;
    //     } else if (file.isPdf) {
    //         modalBody.innerHTML = `
    //             <object data="${file.dataUrl}" type="application/pdf" width="100%" height="550px">
    //                 <p>Tu navegador no soporta la visualización de PDFs. <a href="${file.dataUrl}" download="${file.name}">Descargar archivo</a></p>
    //             </object>
    //         `;
    //     } else {
    //         modalBody.innerHTML = `
    //             <div class="text-center py-5">
    //                 <i class="bi bi-file-earmark-text display-1 text-muted"></i>
    //                 <h6 class="mt-3">${file.name}</h6>
    //                 <a href="${file.dataUrl}" download="${file.name}" class="btn btn-primary mt-2">
    //                     <i class="bi bi-download me-1"></i> Descargar Documento
    //                 </a>
    //             </div>
    //         `;
    //     }

    //     const modal = new bootstrap.Modal(modalEl);
    //     modal.show();
    // }


    //capturar click btn registrar
    document.addEventListener('click', (e) => {
        if (e.target && e.target.closest('#btn-registrar-incremento')) {
            e.preventDefault();
            getData();
            // ejecutarRegistroIncremento();
        }
    });
    
    /**
     * Obtener los datos de la solicitud
     */
    function getData() {
        console.log(ahorrosState)
        // 1. Validar persona seleccionada
        if (!ahorrosState.selectedPerson) {
            Swal.fire('Error', 'Por favor selecciona una persona antes de registrar.', 'error');
            document.getElementById('input-search-persona')?.focus();
            return;
        }

        // 2. Validar cuenta seleccionada entre las 3 opciones
        if (!ahorrosState.selectedAccount) {
            Swal.fire('Error', 'Por favor selecciona una cuenta de ahorro antes de registrar.', 'error');
            return;
        }

        // 3. Validar monto en Pesos Chilenos (debe ser entero y mayor a cero)
        const monto = Math.round(Number(ahorrosState.incrementAmount) || 0);
        if (monto <= 0) {
            Swal.fire('Error', 'Por favor ingresa un monto a incrementar mayor a $0.', 'error');
            document.getElementById('input-monto-incremento')?.focus();
            return;
        }

        // 4. Obtener campos complementarios
        const numeroOperacion = document.getElementById('input-ref-operacion')?.value.trim();
        const fechaOperacion = document.getElementById('input-fecha-operacion')?.value;

        const formData = new FormData();

        formData.append('monto', monto);
        formData.append('numero_operacion', numeroOperacion);
        formData.append('fecha_operacion', fechaOperacion);
        formData.append('cuenta', ahorrosState.selectedAccount.contribution_type_id);
        formData.append('persona', ahorrosState.selectedPerson.id_person);
        formData.append('socio', ahorrosState.selectedPerson.id_partner);
        formData.append('codigo_funcionario', ahorrosState.selectedPerson.codigo_funcionario);
        ahorrosState.attachedFiles.forEach(f => {
            const file = dataURLtoFile(f.dataUrl, f.name);
            formData.append('adjuntos', file);
        });

        
    }




})





