/**
 * CONTROLADOR PRINCIPAL PARA DATATABLES Y EDICIÓN EN MODAL (ASIENTOS PERIODO)
 */

//capturar el crftoken para las solicitudes
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

document.addEventListener('DOMContentLoaded', () => {

    let dataTableInstance = null;
    let dataTableViewAux = null;
    let asientosData = [];
    let activeEditRowId = null;
    let modalRowCounter = 1;

    // Elementos DOM del Modal de Edición
    const modalEditEl = document.getElementById('modal-edit-asiento');
    const modalEdit = new bootstrap.Modal(modalEditEl);
    const modalProcesoEl = document.getElementById('modal-proceso-origen');
    const modalProceso = modalProcesoEl ? new bootstrap.Modal(modalProcesoEl) : null;
    const modalZoomEl = document.getElementById('modal-zoom-doc');
    const modalZoom = modalZoomEl ? new bootstrap.Modal(modalZoomEl) : null;
    const tbodyModalMovements = document.getElementById('tbody-modal-edit-movements');
    const modalEditTotalDebe = document.getElementById('modal-edit-total-debe');
    const modalEditTotalHaber = document.getElementById('modal-edit-total-haber');
    const modalEditDiferencia = document.getElementById('modal-edit-diferencia');
    const modalEditStatusPill = document.getElementById('modal-edit-status-pill');

    // Modal de Cuentas para selección en edición
    const modalAccountsEl = document.getElementById('modal-accounts-dt');
    const modalAccounts = new bootstrap.Modal(modalAccountsEl);
    const inputSearchAccDt = document.getElementById('search-acc-dt');
    const tbodyAccountsDt = document.getElementById('tbody-accounts-dt-catalog');

    /**
     * Formatear número a moneda (2 decimales)
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
     * Convertir texto formateado a número flotante
     */
    function parseMoney(val) {
        if (!val) return 0;
        if (typeof val === 'number') return isNaN(val) ? 0 : Math.round(val);
        
        // Remueve el símbolo $, puntos de miles, espacios y cualquier carácter no numérico excepto el signo menos (-)
        const cleaned = val.toString().replace(/[^0-9-]/g, '');
        const parsed = parseInt(cleaned, 10);
        
        return isNaN(parsed) ? 0 : parsed;
    }

    //SEPARADOR DE MILES
    const formatMiles = (input) => {
        let num = input.value.replace(/\./g, '').replace(/^0+/, '');

        if (!num) {
            input.value = '';
            return;
        }

        if (!/^\d+$/.test(num)) {
            Swal.fire({
                icon: 'warning',
                title: 'Solo se permiten números',
            })
            input.value = '';
            return;
        }

        input.value = num
            .split('')
            .reverse()
            .join('')
            .replace(/(\d{3})(?=\d)/g, '$1.')
            .split('')
            .reverse()
            .join('');
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

    //captura evento input con la clase input-currency
    ['change', 'keyup'].forEach(eventName => {
        document.addEventListener(eventName, (e) => {
            if (e.target && e.target.classList.contains('input-currency')) {
                formatMiles(e.target);
            }
        });
    });

    /**
     * Obtener HTML del badge de Tipo de Asiento
     */
    function getTypeBadge(tipo) {
        const t = (tipo || 'DIARIO').toUpperCase();
        const map = {
            'APERTURA': { class: 'badge-type-apertura', icon: 'bi-door-open', label: 'Apertura' },
            'INGRESO': { class: 'badge-type-ingreso', icon: 'bi-cash-coin', label: 'Ingreso' },
            'EGRESO': { class: 'badge-type-egreso', icon: 'bi-credit-card', label: 'Egreso' },
            'TRASPASO': { class: 'badge-type-diario', icon: 'bi-calendar-event', label: 'Traspaso' },
            'AJUSTE': { class: 'badge-type-ajuste', icon: 'bi-sliders', label: 'Ajuste' },
            'CIERRE': { class: 'badge-type-cierre', icon: 'bi-lock', label: 'Cierre' }
        };
        const conf = map[t] || { class: 'badge-type-diario', icon: 'bi-tag', label: t };
        return `<span class="badge-type ${conf.class}"><i class="bi ${conf.icon}"></i> ${conf.label}</span>`;
    }

    /**
     * Obtener HTML del badge de Estado
     */
    function getStatusBadge(estado) {
        const e = (estado || 'BORRADOR').toUpperCase();
        if (e === 'CONTABILIZADO') {
            return `<span class="badge-status badge-status-contabilizado"><i class="bi bi-check-circle-fill"></i> Contabilizado</span>`;
        } else if (e === 'BORRADOR') {
            return `<span class="badge-status badge-status-borrador"><i class="bi bi-pencil-square"></i> Borrador</span>`;
        } 
        return `<span class="badge bg-secondary">${e}</span>`;
    }

    /**
     * Cargar y actualizar KPIs
     */
    function updateKPIs(items) {
        // console.log(items);
        const totalAsientos = items.length;
        let totalLineas = 0;
        let sumDebe = 0;
        let sumHaber = 0;
        let descuadres = 0;

        items.forEach(a => {
            totalLineas += (a.movimientos || []).length;
            a.movimientos.forEach(m => {
                sumDebe += (m.debe || 0);
                sumHaber += (m.haber || 0);
            })
        });

        $('#kpi-dt-total-asientos').text(totalAsientos);
        $('#kpi-dt-total-lineas').text(`${totalLineas} movimientos registrados`);
        $('#kpi-dt-total-debe').text(formatMoney(sumDebe));
        $('#kpi-dt-total-haber').text(formatMoney(sumHaber));

        if (totalAsientos === 0) {
            $('#kpi-dt-status-text').text('Sin Datos').attr('class', 'kpi-value text-secondary');
            $('#kpi-dt-balance-details').text('No hay registros');
        } else if (descuadres === 0) {
            $('#kpi-dt-status-text').text('100% Cuadrado').attr('class', 'kpi-value text-success');
            $('#kpi-dt-balance-details').text('Partida equilibrada');
            $('#kpi-dt-icon-balance').html('<i class="bi bi-shield-check"></i>');
        } else {
            $('#kpi-dt-status-text').text(`${descuadres} Descuadrado(s)`).attr('class', 'kpi-value text-danger');
            $('#kpi-dt-balance-details').text('Revisar asientos con diferencia');
            $('#kpi-dt-icon-balance').html('<i class="bi bi-exclamation-triangle-fill"></i>');
        }
    }

    /**
     * Renderizador de Subfilas (Child Rows) en DataTables para ver detalle de movimientos
     */
    function formatChildRow(asiento) {
        let movRows = '';
        let totalDebe = 0;
        let totalHaber = 0;
        let is_auxiliar = false;
        let btn_aux = '';
        let btnEdit = '';
        let origen = '';
        if (asiento.is_null) {
            movRows =`
                <tr>
                    <td colspan="8" class="text-center text-muted"><span class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i>Asiento contable NULO</span></td>
                </tr>
            `;
        }

        if (!asiento.aprobacion && !asiento.is_null && asiento.id_asiento_tipo==6) {
            btnEdit = `
                <button class="btn btn-warning btn-sm py-0 px-2 fw-semibold btn-child-edit" data-asiento="${asiento.id}">
                    <i class="bi bi-pencil-square"></i> Editar Asiento
                </button>
            `;
        }

        // if (asiento.origen) {
        //     origen = `
        //     <button type="button" class="btn btn-sm btn-doc-ref-trigger btn-origen d-inline-flex align-items-center gap-1 font-monospace" id="${asiento.id}" title="Clic para ver proceso de origen y documentos adjuntos">
        //         <i class="bi bi-file-earmark-ruled"></i>
        //         <span>${asiento.origen.voucher_number}</span>
        //     </button>
        //     `;
        // }

        (asiento.movimientos || []).forEach((m, idx) => {
            totalDebe += m.debe;
            totalHaber += m.haber;
            is_auxiliar = (m.auxiliares).length > 0;
            if (is_auxiliar){
                btn_aux = `<button type="button" class="btn btn-sm btn-outline-secondary btn-view-aux" data-id="${m.id}" data-asiento="${asiento.id}">
                <i class="bi bi-person"></i> Ver Auxiliares</button>`
            } else {
                btn_aux = '';
            }
            
            movRows += `
                <tr>
                    <td class="text-center text-muted" style="width: 35px;">${idx + 1}</td>
                    <td class="fw-bold font-monospace text-primary" style="width: 90px;">${m.cuenta.num_cuenta}</td>
                    <td class="fw-semibold">${m.cuenta.nombre || '-'}</td>
                    <td class="text-muted" style="width: 120px;">${btn_aux || '-'}</td>
                    <td>${m.glosa}</td>
                    <td class="text-end cell-currency text-primary" style="width: 120px;">${m.debe > 0 ? formatMoney(m.debe) : '-'}</td>
                    <td class="text-end cell-currency text-success" style="width: 120px;">${m.haber > 0 ? formatMoney(m.haber) : '-'}</td>
                </tr>
            `; 
        });

        return `
            <div class="dt-child-container">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="small fw-bold text-uppercase text-secondary">
                        <i class="bi bi-diagram-3 text-primary"></i> Detalle de Movimientos: ${asiento.numero_comprobante}
                    </span>
                    <div class="d-flex gap-2">
                        <span class="badge bg-white text-dark border">Moneda: <strong>CLP</strong></span>
                        <span class="badge bg-white text-dark border">Líneas: <strong>${(asiento.movimientos || []).length}</strong></span>
                        ${btnEdit}
                    </div>
                </div>
                <div class="table-responsive">
                    <table class="table table-sm nested-movements-table table-bordered">
                        <thead>
                            <tr>
                                <th class="text-center">#</th>
                                <th>Código</th>
                                <th>Denominación de Cuenta</th>
                                <th>Auxiliar</th>
                                <th>Glosa Específica</th>
                                <th class="text-end text-primary">Debe ($)</th>
                                <th class="text-end text-success">Haber ($)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${movRows}
                        </tbody>
                        <tfoot class="table-light fw-bold">
                            <tr>
                                <td colspan="5" class="text-end text-uppercase">Sumas del Asiento:</td>
                                <td class="text-end cell-currency text-primary">${formatMoney(totalDebe)}</td>
                                <td class="text-end cell-currency text-success">${formatMoney(totalHaber)}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>
        `;
    }

    //capturar click btn ver aux
    document.addEventListener('click', (e) => {
        if(e.target && e.target.closest('.btn-view-aux')) {
            e.preventDefault();
            const target = e.target.closest('.btn-view-aux');
            const idAsiento = Number(target.dataset.asiento);
            const idMovimiento = Number(target.dataset.id);

            // //buscar los auxiliares
            // 1. Buscar el asiento
            const asientoEncontrado = asientosData.find(a => a.id === idAsiento);

            // 2. Buscar el movimiento dentro del asiento encontrado (si existe)
            const movimientoEncontrado = asientoEncontrado?.movimientos?.find(m => m.id === idMovimiento);

            // 3. Obtener auxiliares o asignar un array vacío si no existe
            const auxiliares = movimientoEncontrado?.auxiliares ?? [];

            viewAux(auxiliares);
        }
    })

    //capturar click btn origen
    document.addEventListener('click', (e) => {
        if(e.target && e.target.closest('.btn-origen')) {
            e.preventDefault();
            const target = e.target.closest('.btn-origen');
            const id_asiento = Number(target.id);

            // 1. Buscar el asiento
            const asientoEncontrado = asientosData.find(a => a.id === id_asiento);
            if (asientoEncontrado) {
                viewOrigen(asientoEncontrado);
            } else {
                Swal.fire({
                    icon: 'warning',
                    title: 'No se encontraron documentos adjuntos.',
                })
            }
        }
    })

    //ver origen
    const viewOrigen = (data) => {
        if (data.length == 0 || data == null) {
            return
        }

        // 1. Encabezado del modal
        const badgeTipo = document.getElementById('modal-proc-badge-tipo');
        if (badgeTipo) {
            badgeTipo.innerHTML = getTypeBadge(data.asiento_tipo);
        }

        document.getElementById('modal-proc-asiento-num').textContent = data.numero_asiento;
        document.getElementById('modal-proc-ref-doc').textContent = data.origen.voucher_number;
        document.getElementById('modal-proc-fecha').textContent = data.fecha_asiento;

        document.getElementById('modal-proc-categoria').textContent = data.asiento_tipo;
        document.getElementById('modal-proc-nombre').textContent = data.origen.process_type.description;
        document.getElementById('modal-proc-glosa').textContent = data.origen.description || data.glosa;

        document.getElementById('modal-proc-monto').textContent = `${formatMoney(data.origen.amount)}`;

        const estadoBadge = document.getElementById('modal-proc-estado');
        if (estadoBadge) {
            estadoBadge.textContent = data.asiento_estado;
            if (data.asiento_estado === 'CONTABILIZADO') estadoBadge.className = 'badge bg-success-subtle text-success border border-success-subtle fs-xs';
            else if (data.asiento_estado === 'BORRADOR') estadoBadge.className = 'badge bg-warning-subtle text-warning border border-warning-subtle fs-xs';
            else estadoBadge.className = 'badge bg-danger-subtle text-danger border border-danger-subtle fs-xs';
        }

        // Metadatos
        document.getElementById('modal-proc-tercero').textContent = data.origen.process_type.description;
        document.getElementById('modal-proc-tercero-id').textContent = data.origen.voucher_number;
        document.getElementById('modal-proc-socio').textContent = data.origen.application.partner.person;
        document.getElementById('modal-proc-socio-detalle').textContent = data.origen.application.partner.rut;
        document.getElementById('modal-proc-module').textContent = data.origen.module;
        document.getElementById('modal-proc-usuario').textContent = data.origen.user_create;
        document.getElementById('modal-proc-creado').textContent = data.origen.created_at;

        // 4. Documentos y Respaldo Adjuntos
        const containerAdjuntos = document.getElementById('modal-proc-adjuntos-list');
        const badgeTotalAdj = document.getElementById('modal-proc-total-adjuntos');
        if (badgeTotalAdj) {
            badgeTotalAdj.textContent = `${data.origen.documents.length} archivo${data.origen.documents.length === 1 ? '' : 's'}`;
        }

        if (containerAdjuntos) {
            if (data.origen.documents === 0) {
                containerAdjuntos.innerHTML = `
                    <div class="text-center py-4 text-muted">
                        <i class="bi bi-folder-x fs-2 d-block mb-2 text-secondary opacity-50"></i>
                        <p class="small mb-0">No se encontraron archivos anexados para esta referencia.</p>
                    </div>
                `;
            } else {
                let adjuntosHtml = '';
                data.origen.documents.forEach(file => {
                    let previewElement = '';
                    if (file.file_type === 'image' && file.url) {
                        previewElement = `
                            <img src="${file.url}" alt="${file.internal_name}" class="attachment-thumb-img shadow-sm"
                                 data-img="${file.url}" data-title="${file.internal_name}" title="Clic para ver en pantalla completa">
                        `;
                    } else if (file.file_type == 'application/pdf') {
                        previewElement = `
                            <div class="attachment-icon-box bg-danger-subtle text-danger border border-danger-subtle shadow-sm">
                                <i class="bi bi-file-earmark-pdf-fill"></i>
                            </div>
                        `;
                    } else {
                        previewElement = `
                            <div class="attachment-icon-box bg-primary-subtle text-primary border border-primary-subtle shadow-sm">
                                <i class="bi bi-file-earmark-text-fill"></i>
                            </div>
                        `;
                    }

                    adjuntosHtml += `
                        <div class="attachment-preview-card">
                            <div class="d-flex align-items-center gap-3 overflow-hidden">
                                ${previewElement}
                                <div class="overflow-hidden">
                                    <div class="fw-bold text-dark fs-sm text-truncate" title="${file.name}">
                                        ${file.name}
                                    </div>
                                    <div class="text-muted fs-xs mt-1">
                                        <span><i class="bi bi-hdd-network me-1"></i>${formatBytes(file.size)}</span>
                                        <span class="mx-1">•</span>
                                    </div>
                                </div>
                            </div>
                            <div class="d-flex align-items-center gap-1 flex-shrink-0">
                                ${file.file_type === 'image' && file.url ? `
                                    <button type="button" class="btn btn-outline-primary btn-sm py-1 px-2 d-flex align-items-center gap-1 btn-zoom-file" data-img="${file.url}" data-title="${file.internal_name}">
                                        <i class="bi bi-zoom-in"></i> Ver
                                    </button>
                                ` : ''}
                                <a href="${file.url || '#'}" target="_blank" download="${file.name}" class="btn btn-primary btn-sm py-1 px-2 d-flex align-items-center gap-1 btn-download-file ${!file.url ? 'disabled' : ''}">
                                    <i class="bi bi-download"></i> Descargar
                                </a>
                            </div>
                        </div>
                    `;
                });
                containerAdjuntos.innerHTML = adjuntosHtml;

                // Listeners de zoom para miniaturas e imágenes
                containerAdjuntos.querySelectorAll('.attachment-thumb-img, .btn-zoom-file').forEach(el => {
                    el.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const url = el.getAttribute('data-img');
                        const title = el.getAttribute('data-title');
                        openZoomDocModal(url, title);
                    });
                });
            }
        }

        if (modalProceso) {
            modalProceso.show();
        }
    }

    function openZoomDocModal(dataUrl, title) {
        const imgTarget = document.getElementById('zoom-doc-img');
        const titleTarget = document.getElementById('zoom-doc-title');
        const dlBtn = document.getElementById('btn-zoom-download');

        if (imgTarget) imgTarget.src = dataUrl;
        if (titleTarget) titleTarget.textContent = title || "Vista Previa de Documento";
        if (dlBtn) {
            dlBtn.href = dataUrl;
            dlBtn.download = (title || 'documento').replace(/\s+/g, '_') + '.png';
        }

        if (modalZoom) {
            modalZoom.show();
        }
    }

    //cargar aux en tbl y abrir modal
    const viewAux = (data) => {
        if (data.length == 0 || data == null) {
            return
        }

        if ($.fn.DataTable.isDataTable('#tabla-view-auxiliares-modal')) {
            dataTableViewAux.destroy();
        }

        dataTableViewAux = $('#tabla-view-auxiliares-modal').DataTable({
            data: data,
            responsive: false,
            pageLength: 10,
            lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
            order: [[1, 'asc']],
            language: {
                search: "_INPUT_",
                searchPlaceholder: "Buscar en DataTables...",
                lengthMenu: "Mostrar registros _MENU_",
                info: "Mostrando _START_ a _END_ de _TOTAL_ asientos",
                infoEmpty: "Mostrando 0 a 0 de 0 asientos",
                infoFiltered: "(filtrado de _MAX_ registros totales)",
                zeroRecords: "No se encontraron asientos contables coincidentes",
                paginate: {
                    first: "«",
                    previous: "‹",
                    next: "›",
                    last: "»"
                }
            },
            columns: [
                { data: 'rut' },
                { data: 'nombre_persona' },
                { data: 'monto',
                    render: function (data) {
                        return `${formatMoney(data)}`;
                    }
                 },
            ],
            initComplete: function () {
                $('#modal-view-aux').modal('show');
            }
        });
    }

    /**
     * Inicializar DataTables con opciones en español y botones de acción
     */

    //obtener data de asientos
    const getAsientosFromStorage = async() => {
        // Spinner de carga
        Swal.fire({
            title: "Espere",
            text: "Cargando datos...",
            allowOutsideClick: false,
            showConfirmButton: false,
            willOpen: () => {
                Swal.showLoading();
            },
        });
        try {
            const response = await fetch('/contabilidad/asientos_contables/asiento_periodo/all/', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                }
            });

            const data = await response.json();
            Swal.close();
            console.log(data);
            if (data.success) {
                asientosData = data.data;
                initDataTable();
                // return data.data;
            } else {
                throw new Error(data.message || 'No es posible obtener los asientos');
            }

        } catch (error) {
            console.error(error);
            Swal.fire({
                icon: 'error',
                title: 'Error al obtener los asientos',
                text: error.message
            })
            return [];
        }
    }


    //inicar dataTables
    function initDataTable() {
        //cargar estadisticas
        updateKPIs(asientosData);

        if ($.fn.DataTable.isDataTable('#tabla-asientos-dt')) {
            dataTableInstance.destroy();
        }

        dataTableInstance = $('#tabla-asientos-dt').DataTable({
            data: asientosData,
            responsive: false,
            pageLength: 10,
            lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
            order: [[1, 'asc']],
            language: {
                search: "_INPUT_",
                searchPlaceholder: "Buscar en DataTables...",
                lengthMenu: "Mostrar registros _MENU_",
                info: "Mostrando _START_ a _END_ de _TOTAL_ asientos",
                infoEmpty: "Mostrando 0 a 0 de 0 asientos",
                infoFiltered: "(filtrado de _MAX_ registros totales)",
                zeroRecords: "No se encontraron asientos contables coincidentes",
                paginate: {
                    first: "«",
                    previous: "‹",
                    next: "›",
                    last: "»"
                }
            },
            columns: [
                {
                    className: 'dt-control text-center',
                    orderable: false,
                    data: null,
                    defaultContent: '<button class="btn btn-sm btn-light border btn-toggle-expand" type="button" title="Ver movimientos"><i class="bi bi-chevron-right"></i></button>',
                    width: '35px'
                },
                {
                    data: 'numero_asiento',
                    render: function (data) {
                        return `<span class="fw-bold font-monospace text-primary">${data}</span>`;
                    }
                },
                { data: 'fecha_asiento', className: 'text-nowrap' },
                {
                    data: 'periodo',
                    render: function (data) {
                        let fecha = data.month_name +' '+data.year
                        return `<span class="badge bg-light text-dark border">${fecha || '-'}</span>`;
                    }
                },
                {
                    data: 'asiento_tipo',
                    render: function (data) {
                        return getTypeBadge(data);
                    }
                },
                {
                    data: 'glosa',
                    render: function (data) {
                        return `<div class="text-truncate" style="max-width: 280px;" title="${data}">${data}</div>`;
                    }
                },
                {
                    data: 'origen',
                    render: function (data, type, row) {
                        if (!data) return '-';
                        return `<button type="button" class="btn btn-outline-secondary btn-sm btn-doc-ref-trigger btn-origen d-inline-flex align-items-center gap-1 font-monospace" id="${row.id}" title="Clic para ver proceso de origen y documentos adjuntos">
                            <i class="bi bi-file-earmark-ruled"></i>
                            <span>${data.voucher_number}</span>
                        </button>`;
                    }
                },
                {
                    data: 'movimientos',
                    className: 'text-end cell-currency text-primary',
                    render: function (data) {
                        let totalDebe = 0;
                        data.forEach(mov => {
                            totalDebe += mov.debe
                        })
                        return formatMoney(totalDebe);
                    }
                },
                {
                    data: 'movimientos',
                    className: 'text-end cell-currency text-success',
                    render: function (data) {
                        let totalHaber = 0;
                        data.forEach(mov => {
                            totalHaber += mov.haber
                        })
                        return formatMoney(totalHaber);
                    }
                },
                {
                    data: 'asiento_estado',
                    className: 'text-center',
                    render: function (data) {
                        return getStatusBadge(data);
                    }
                },
                {
                    data: null,
                    orderable: false,
                    className: 'text-center no-print',
                    render: function (data, type, row) {
                        let btn = `<div class="btn-group btn-group-sm">`

                        if (!row.aprobacion) {
                            btn += `<button class="btn btn-outline-success btn-dt-validate" title="Validar asiento">
                                        <i class="bi bi-check-circle"></i>
                                    </button>`;
                            
                            if (row.id_asiento_tipo == 6) {
                                if (row.is_null) {
                                    btn += `<button class="btn btn-outline-info btn-dt-active" title="Activar asiento">
                                                <i class="bi bi-exclamation-triangle-fill"></i>
                                            </button>`;
                                } else {
                                    btn += `
                                        <button class="btn btn-outline-danger btn-dt-anular" title="Anular Asiento">
                                            <i class="bi bi-slash-circle"></i>
                                        </button>
                                        <button class="btn btn-outline-warning btn-dt-edit" title="Editar en Modal">
                                            <i class="bi bi-pencil-square"></i>
                                        </button>
                                    `;
                                }
                            }
                        } else {
                            btn += `<button class="btn btn-outline-secondary btn-dt-pdf">
                                        <i class="bi bi-printer"></i>
                                    </button>`;
                        }


                        
                        btn += `</div>`;
                        
                        return btn;
                    }
                }
            ]
        });

        // Configurar expansión de subfilas (Child Rows)
        $('#tabla-asientos-dt tbody').off('click', 'td.dt-control button').on('click', 'td.dt-control button', function (e) {
            e.stopPropagation();
            const tr = $(this).closest('tr');
            const row = dataTableInstance.row(tr);
            const btn = $(this);

            if (row.child.isShown()) {
                row.child.hide();
                tr.removeClass('shown dt-hasChild');
                btn.removeClass('expanded');
            } else {
                row.child(formatChildRow(row.data())).show();
                tr.addClass('shown dt-hasChild');
                btn.addClass('expanded');
            }
        });

        // Clic en editar dentro de la fila hija
        $('#tabla-asientos-dt tbody').off('click', '.btn-child-edit').on('click', '.btn-child-edit', function (e) {
            e.stopPropagation();
            const idAsiento = $(this).data('asiento');
            const asiento = asientosData.find(a => a.id === idAsiento);
            if (asiento) {
                Swal.showLoading();
                openEditModal(asiento);
            }
        });

        // btn editar
        $('#tabla-asientos-dt tbody').off('click', '.btn-dt-edit').on('click', '.btn-dt-edit', function (e) {
            e.stopPropagation();
            Swal.showLoading();
            const rowData = dataTableInstance.row($(this).closest('tr')).data();
            openEditModal(rowData);
        });

        //btn anular asiento
        $('#tabla-asientos-dt tbody').off('click', '.btn-dt-anular').on('click', '.btn-dt-anular', function (e) {
            e.stopPropagation();
            const rowData = dataTableInstance.row($(this).closest('tr')).data();
            anularAsiento(rowData.id);
        });

        //btn quitar nulo asiento
        $('#tabla-asientos-dt tbody').off('click', '.btn-dt-active').on('click', '.btn-dt-active', function (e) {
            e.stopPropagation();
            const rowData = dataTableInstance.row($(this).closest('tr')).data();
            quitarNuloAsiento(rowData.id);
        });

        //btn validar asiento
        $('#tabla-asientos-dt tbody').off('click', '.btn-dt-validate').on('click', '.btn-dt-validate', function (e) {
            e.stopPropagation();
            const rowData = dataTableInstance.row($(this).closest('tr')).data();
            validarAsiento(rowData.id);
        });

        //asiento pdf
        $('#tabla-asientos-dt tbody').off('click', '.btn-dt-pdf').on('click', '.btn-dt-pdf', function (e) {
            e.stopPropagation()
            const rowData = dataTableInstance.row($(this).closest('tr')).data();
            generarPdf(rowData.id);
        });
    }

    //generar pdf
    const generarPdf = async (idAsiento) => {
        try {
            const response = await fetch(`/contabilidad/asientos_contables/pdf/${parseInt(idAsiento)}/`, {
                method: 'GET',
                headers: {
                    'Content-Type': "application/json",
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                },
            })

            if (!response.ok) {
                throw new Error("No fue posible generar el PDF.");
            }

            const blob = await response.blob();
            const pdfUrl = URL.createObjectURL(blob);
            window.open(pdfUrl, '_blank');

            setTimeout(() => {
                URL.revokeObjectURL(pdfUrl);
            }, 1000);

        } catch (error) {
            console.error(error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No fue posible generar el PDF.',
            })
        }
    }

    //validar asiento
    const validarAsiento = async(idAsiento) => {
        const result = await Swal.fire({
            title: 'Validar asiento?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33',
            confirmButtonText: 'Si, Validar',
            cancelButtonText: 'Cancelar',
            showLoaderOnConfirm: true,
            allowOutsideClick: () => !Swal.isLoading(),
            preConfirm: async () => {
                Swal.update({
                    title: 'Validando asiento...',
                    text: 'Por favor espere'
                })

                try {
                    const response = await fetch(`/contabilidad/asientos_contables/validate/${parseInt(idAsiento)}/`, {
                        method: 'GET',
                        headers: {
                            'Content-Type': "application/json",
                            'X-CSRFToken': csrftoken,
                            'X-App-Request': 'true'
                        },
                    });

                    const data = await response.json();

                    if (!data.success) {
                        const mensajeError = data.message || data.error || 'Ocurrió un error inesperado al guardar.';
                        Swal.showValidationMessage(mensajeError);
                        return false;
                    }
                    return data;
                } catch (error) {
                    console.error(error);
                    Swal.showValidationMessage(`Error: ${error.message}`);
                }
            }
        });

        if (result.isConfirmed && result.value.success) {
            modalEdit.hide();
            auxiliaresMovimiento = [];
            Swal.fire({
                icon: 'success',
                title: '¡Operación Exitosa!',
                text: result.value.message || 'Asiento contable validado correctamente.',
                showConfirmButton: true,
                confirmButtonText: 'Refrescar y continuar',
                confirmButtonColor: '#3085d6',
                allowOutsideClick: false, // Obliga al usuario a interactuar con el botón
                allowEscapeKey: false     // Evita cerrar con la tecla Escape
            }).then((confirmResult) => {
                if (confirmResult.isConfirmed) {
                    // Se ejecuta únicamente cuando el usuario presiona "Refrescar y continuar"
                    getAsientosFromStorage();
                }
            });
            
        }
    }

    //anular asiento
    const anularAsiento = async (idAsiento) => {
        const result = await Swal.fire({
            title: 'Anular asiento?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33',
            confirmButtonText: 'Si, Anular',
            cancelButtonText: 'Cancelar',
            showLoaderOnConfirm: true,
            allowOutsideClick: () => !Swal.isLoading(),
            preConfirm: async () => {
                Swal.update({
                    title: 'Anulando asiento...',
                    text: 'Por favor espere'
                })

                try {
                    const response = await fetch(`/contabilidad/asientos_contables/anular/${parseInt(idAsiento)}/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': "application/json",
                            'X-CSRFToken': csrftoken,
                            'X-App-Request': 'true'
                        },
                    });

                    const data = await response.json();

                    if (!data.success) {
                        const mensajeError = data.message || data.error || 'Ocurrió un error inesperado al guardar.';
                        Swal.showValidationMessage(mensajeError);
                        return false;
                    }
                    
                    return data;

                } catch (error) {
                    console.error(error);
                    Swal.showValidationMessage(`Error: ${error.message}`);
                }
            }
        });

        if (result.isConfirmed && result.value.success) {
            modalEdit.hide();
            auxiliaresMovimiento = [];
            Swal.fire({
                icon: 'success',
                title: '¡Operación Exitosa!',
                text: result.value.message || 'Asiento contable anulado correctamente.',
                showConfirmButton: true,
                confirmButtonText: 'Refrescar y continuar',
                confirmButtonColor: '#3085d6',
                allowOutsideClick: false, // Obliga al usuario a interactuar con el botón
                allowEscapeKey: false     // Evita cerrar con la tecla Escape
            }).then((confirmResult) => {
                if (confirmResult.isConfirmed) {
                    // Se ejecuta únicamente cuando el usuario presiona "Refrescar y continuar"
                    getAsientosFromStorage();
                }
            });
            
        }
    }

    //anular asiento
    const quitarNuloAsiento = async (idAsiento) => {
        const result = await Swal.fire({
            title: 'Quitar nulo asiento?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33',
            confirmButtonText: 'Si, Volver a activar',
            cancelButtonText: 'Cancelar',
            showLoaderOnConfirm: true,
            allowOutsideClick: () => !Swal.isLoading(),
            preConfirm: async () => {
                Swal.update({
                    title: 'Activando asiento...',
                    text: 'Por favor espere'
                })

                try {
                    const response = await fetch(`/contabilidad/asientos_contables/quitar_nulo_asiento/${parseInt(idAsiento)}/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': "application/json",
                            'X-CSRFToken': csrftoken,
                            'X-App-Request': 'true'
                        },
                    });

                    const data = await response.json();
                    console.log(data)

                    if (!data.success) {
                        const mensajeError = data.message || data.error || 'Ocurrió un error inesperado al guardar.';
                        Swal.showValidationMessage(mensajeError);
                        return false;
                    }
                    
                    return data;

                } catch (error) {
                    console.error(error);
                    Swal.showValidationMessage(`Error: ${error.message}`);
                }
            }
        });

        if (result.isConfirmed && result.value.success) {
            modalEdit.hide();
            auxiliaresMovimiento = [];
            Swal.fire({
                icon: 'success',
                title: '¡Operación Exitosa!',
                text: result.value.message || 'Asiento contable activado correctamente.',
                showConfirmButton: true,
                confirmButtonText: 'Refrescar y continuar',
                confirmButtonColor: '#3085d6',
                allowOutsideClick: false, // Obliga al usuario a interactuar con el botón
                allowEscapeKey: false     // Evita cerrar con la tecla Escape
            }).then((confirmResult) => {
                if (confirmResult.isConfirmed) {
                    // Se ejecuta únicamente cuando el usuario presiona "Refrescar y continuar"
                    getAsientosFromStorage();
                }
            });
            
        }
    }

    //cerrar modal edicion y quitar bloqueo
    document.addEventListener('click', async (e) => {
        if (e.target && e.target.closest('.btn-close-modal-edit')) {
            e.preventDefault();
            const idAsiento = document.getElementById('modal-edit-id').value;
            try {
                const response = await fetch(`/contabilidad/asientos_contables/uncheck_edit/${parseInt(idAsiento)}/`, {
                    method: 'GET',
                    headers: {
                        'X-CSRFToken': csrftoken,
                        'X-App-Request': 'true'
                    },
                })
                const data = await response.json();
                console.log(data);
                modalEdit.hide();
                auxiliaresMovimiento = [];
                if (!data.success) {
                    getAsientosFromStorage();
                }
            } catch (error) {
                console.error(error);
            }
        }
    })


    // =========================================================================
    // MODAL DE EDICIÓN: GESTIÓN DE CABECERA Y MOVIMIENTOS CONTABLES EN VIVO
    // =========================================================================

    /**
     * Verificar si se puede editar asiento y Abrir Modal de Edición cargando los datos del asiento
     */
    const openEditModal = async (asiento) => {
        try {
            const formData = new FormData();
            formData.append('idAsiento', asiento.id);
            formData.append('version', asiento.version);
            const response = await fetch(`/contabilidad/asientos_contables/check_edit/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                },
                body: formData
            });
            const data = await response.json();
            console.log(data);
            if (!data.success) {
                Swal.fire({
                    icon: 'warning',
                    title: data.message || 'Asiento contable fue modificado por otro usuario.',
                    showConfirmButton: true,
                    confirmButtonText: 'Continuar',
                    confirmButtonColor: '#3085d6',
                    allowOutsideClick: false, // Obliga al usuario a interactuar con el botón
                    allowEscapeKey: false     // Evita cerrar con la tecla Escape
                }).then((confirmResult) => {
                    if (confirmResult.isConfirmed) {
                        // Se ejecuta únicamente cuando el usuario presiona "Refrescar y continuar"
                        data.refresh ? getAsientosFromStorage() : '';
                    }
                });
            } else {
                // Clonar para edición
                const cloned = JSON.parse(JSON.stringify(asiento));
                // asientoEdit = cloned;

                document.getElementById('modal-edit-id').value = cloned.id;
                document.getElementById('modal-edit-num').value = cloned.numero_asiento;
                document.getElementById('modal-edit-voucher').value = cloned.numero_comprobante;
                document.getElementById('modal-edit-fecha').value = cloned.fecha_asiento;
                document.getElementById('modal-edit-periodo').value = cloned.periodo.month_name + ' ' + cloned.periodo.year;
                document.getElementById('modal-edit-tipo').value = cloned.asiento_tipo;
                document.getElementById('modal-edit-glosa').value = cloned.glosa;

                // Badge de estado en modal
                const badge = document.getElementById('modal-edit-badge-estado');
                badge.textContent = cloned.asiento_estado;
                badge.className = 'badge bg-warning text-dark';

                // Limpiar tabla de movimientos del modal y cargar los movimientos
                tbodyModalMovements.innerHTML = '';
                modalRowCounter = 1;

                if (Array.isArray(cloned.movimientos) && cloned.movimientos.length > 0) {
                    cloned.movimientos.forEach(m => createModalMovementRow(m));
                }

                recalculateModalTotals();
                modalEdit.show();
            }

        } catch (error) {
            console.error(error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.message || 'Ocurrió un error al obtener los datos del asiento.',
            })
            return;
        } finally {
            Swal.close();
        }
        
    }

    /**
     * Crear una fila de movimiento dentro de la grilla del modal
     */
    function createModalMovementRow(data = {}) {
        const rowId = modalRowCounter++;
        const tr = document.createElement('tr');
        tr.className = 'modal-mov-row';
        tr.dataset.modalRowId = rowId;

        const defaultGlosa = data?.glosa || $('#modal-edit-glosa').val().toUpperCase() || '';
        const defaultDebe = data?.debe !== undefined ? data.debe : 0;
        const defaultHaber = data?.haber !== undefined ? data.haber : 0;
        const defaultCodigoCuenta = data.cuenta?.num_cuenta ?? '';
        const cuentaMov = data.cuenta?.id ?? '';
        const movId = data?.id ?? `M${rowId}`;

        const disabled = data.cuenta?.is_auxiliar ? '' : 'disabled';

        //auxiliares
        const auxiliares = data?.auxiliares ?? false;

        //cargar auxiliares a array aux
        if (auxiliares) {
            auxiliares.forEach(aux => {
                auxiliaresMovimiento.push({
                    person: Number(aux.id_persona),
                    rut: aux.rut,
                    nombre: aux.nombre_persona,
                    amount: aux.monto,
                    account: Number(cuentaMov),
                    movId: movId
                });
            })
        }

        // Buscar nombre de la cuenta
        let accountName = "Seleccione cuenta...";
        if (defaultCodigoCuenta && typeof obtenerCuentaPorCodigo === 'function') {
            const acc = obtenerCuentaPorCodigo(defaultCodigoCuenta);
            if (acc) accountName = acc.nombre;
        }

        tr.innerHTML = `
            <td class="text-center align-middle">
                <span class="badge bg-light text-secondary border modal-row-number">0</span>
            </td>
            <td>
                <div class="input-group input-group-sm input-account-group">
                    <button class="btn btn-outline-secondary btn-modal-search-acc py-0 px-2" type="button" title="Buscar en catálogo">
                        <i class="bi bi-search"></i>
                    </button>
                    <input type="text" class="form-control form-control-sm modal-input-codigo" 
                           placeholder="Código" value="${defaultCodigoCuenta}" list="list-cuentas" maxlength="15" style="max-width: 85px; font-weight: 600;">
                    <input type="text" class="form-control form-control-sm modal-input-nombre bg-light" 
                           placeholder="Nombre cuenta" value="${accountName !== 'Seleccione cuenta...' ? accountName : ''}" readonly>
                    <input type="hidden" class="input-cuenta-id" value="${cuentaMov}" data-mov-id="${movId}">
                </div>
            </td>
            <td>
                <input type="text" class="form-control form-control-sm modal-input-glosa py-1" placeholder="Detalle línea" value="${defaultGlosa}">
            </td>
            <td>
                <input type="text" class="form-control form-control-sm input-currency input-debe py-1 modal-input-debe" 
                       placeholder="0" value="${defaultDebe > 0 ? formatMoney(defaultDebe) : ''}">
            </td>
            <td>
                <input type="text" class="form-control form-control-sm input-currency input-haber py-1 modal-input-haber" 
                       placeholder="0" value="${defaultHaber > 0 ? formatMoney(defaultHaber) : ''}">
            </td>
            <td class="text-center align-middle">
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary btn-modal-add-auxiliar-row" type="button" title="Agregar auxiliar" ${disabled}>
                        <i class="bi bi-person"></i>
                    </button>
                    <button class="btn btn-outline-danger py-0 px-2 btn-modal-del-row" type="button" title="Eliminar">
                        <i class="bi bi-trash3"></i>
                    </button>
                </div>
            </td>
        `;

        setupModalRowEvents(tr);
        tbodyModalMovements.appendChild(tr);
        renumberModalRows();
        recalculateModalTotals();

        return tr;
    }

    //obtener elnombre de la cuenta
    function obtenerCuentaPorCodigo(codigo) {
        return CATALOGO_CUENTAS.find(c => c.num_cuenta === codigo) || null;
    }

    /**
     * Eventos de cada fila dentro del modal de edición
     */
    function setupModalRowEvents(tr) {
        const inputCodigo = tr.querySelector('.modal-input-codigo');
        const inputNombre = tr.querySelector('.modal-input-nombre');
        const inputCuentaId = tr.querySelector('.input-cuenta-id');
        const inputMovId = tr.querySelector('.input-cuenta-id').dataset.movId;
        const btnSearch = tr.querySelector('.btn-modal-search-acc');
        const inputDebe = tr.querySelector('.modal-input-debe');
        const inputHaber = tr.querySelector('.modal-input-haber');
        const btnDel = tr.querySelector('.btn-modal-del-row');
        const btnAux = tr.querySelector('.btn-modal-add-auxiliar-row');

        // Búsqueda en catálogo modal
        btnSearch.addEventListener('click', () => {
            activeEditRowId = tr.dataset.modalRowId;
            openAccountsCatalogModal();
        });

        // Cambio de código de cuenta directo
        inputCodigo.addEventListener('input', () => {
            const code = inputCodigo.value.trim();
            if (typeof obtenerCuentaPorCodigo === 'function') {
                const acc = obtenerCuentaPorCodigo(code);
                if (acc) {
                    inputNombre.value = acc.nombre;
                    inputCuentaId.value = acc.id;
                    inputCodigo.classList.remove('is-invalid');
                    inputCodigo.classList.add('is-valid');
                    btnAux.disabled = (acc.is_auxiliar == true) ? false : true;
                } else {
                    inputNombre.value = '';
                    inputCuentaId.value = '';
                    inputCodigo.classList.remove('is-valid');
                    if (code.length >= 3) inputCodigo.classList.add('is-invalid');
                    else inputCodigo.classList.remove('is-invalid');
                }
            }
        });

        // Eventos Debe
        inputDebe.addEventListener('focus', (e) => {
            const val = parseMoney(e.target.value);
            e.target.value = val === 0 ? '' : val;
        });

        inputDebe.addEventListener('blur', (e) => {
            const val = parseMoney(e.target.value);
            if (val > 0) {
                e.target.value = formatMoney(val);
                inputHaber.value = '';
            } else {
                e.target.value = '';
            }
            recalculateModalTotals();
        });

        inputDebe.addEventListener('keyup', () => recalculateModalTotals());

        // Eventos Haber
        inputHaber.addEventListener('focus', (e) => {
            const val = parseMoney(e.target.value);
            e.target.value = val === 0 ? '' : val;
        });

        inputHaber.addEventListener('blur', (e) => {
            const val = parseMoney(e.target.value);
            if (val > 0) {
                e.target.value = formatMoney(val);
                inputDebe.value = '';
            } else {
                e.target.value = '';
            }
            recalculateModalTotals();
        });

        inputHaber.addEventListener('keyup', () => recalculateModalTotals());

        // Eliminar fila en modal
        btnDel.addEventListener('click', () => {
            tr.remove();
            //quitar los auxiliares de la fila eliminada
            auxiliaresMovimiento = auxiliaresMovimiento.filter(auxiliar => !(auxiliar.account === Number(inputCuentaId.value) && auxiliar.movId == inputMovId));
            renumberModalRows();
            recalculateModalTotals();
            Swal.fire({
                icon: 'success',
                title: 'Fila eliminada',
                text: 'Fila de movimiento eliminada del asiento.',
            });
        });

        // Abrir modal de auxiliares
        btnAux.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById("cuenta-seleccionada-modal").value = inputCuentaId.value;
            document.getElementById("cuenta-seleccionada-modal").dataset.movId = inputMovId;
            renderizarTblAux();
            $('#modal-add-auxiliares').modal('show');
        });
    }

    /**
     * Renumerar filas en el modal de edición
     */
    function renumberModalRows() {
        const rows = tbodyModalMovements.querySelectorAll('tr');
        rows.forEach((r, idx) => {
            const numBadge = r.querySelector('.modal-row-number');
            if (numBadge) numBadge.textContent = idx + 1;
        });
    }

    /**
     * Recalcular totales y estado de balance dentro del modal
     */
    function recalculateModalTotals() {
        let sumDebe = 0;
        let sumHaber = 0;

        const rows = tbodyModalMovements.querySelectorAll('tr');
        rows.forEach(r => {
            sumDebe += parseMoney(r.querySelector('.modal-input-debe')?.value);
            sumHaber += parseMoney(r.querySelector('.modal-input-haber')?.value);
        });

        const diff = sumDebe - sumHaber;

        modalEditTotalDebe.textContent = formatMoney(sumDebe);
        modalEditTotalHaber.textContent = formatMoney(sumHaber);
        modalEditDiferencia.textContent = formatMoney(diff);

        if (sumDebe === 0 && sumHaber === 0) {
            modalEditStatusPill.className = 'status-pill bg-secondary text-white';
            modalEditStatusPill.innerHTML = '<i class="bi bi-circle"></i> SIN MONTOS';
            document.getElementById('btn-modal-save-post').disabled = true;
        } else if (diff === 0) {
            modalEditStatusPill.className = 'status-pill balanced';
            modalEditStatusPill.innerHTML = '<i class="bi bi-check-circle-fill"></i> ASIENTO CUADRADO';
            document.getElementById('btn-modal-save-post').disabled = false;
        } else {
            modalEditStatusPill.className = 'status-pill unbalanced';
            modalEditStatusPill.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i> DESCUADRADO (${formatMoney(diff)})`;
            document.getElementById('btn-modal-save-post').disabled = true;
        }
    }

    /**
     * Auto-cuadre inteligente dentro del modal
     */
    function autoBalanceModal() {
        let sumDebe = 0;
        let sumHaber = 0;

        const rows = Array.from(tbodyModalMovements.querySelectorAll('tr'));
        rows.forEach(r => {
            sumDebe += parseMoney(r.querySelector('.modal-input-debe')?.value);
            sumHaber += parseMoney(r.querySelector('.modal-input-haber')?.value);
        });

        const diff = sumDebe - sumHaber;

        if (diff === 0) {
            showToast("El asiento ya está perfectamente cuadrado.", "info");
            return;
        }

        // Buscar una fila vacía para colocar el cuadre
        let targetRow = rows.find(r => {
            const d = parseMoney(r.querySelector('.modal-input-debe')?.value);
            const h = parseMoney(r.querySelector('.modal-input-haber')?.value);
            return d === 0 && h === 0;
        });

        if (!targetRow) {
            targetRow = createModalMovementRow();
        }

        const inpD = targetRow.querySelector('.modal-input-debe');
        const inpH = targetRow.querySelector('.modal-input-haber');

        if (diff > 0) {
            inpH.value = formatMoney(diff);
            inpD.value = '';
        } else {
            inpD.value = formatMoney(diff);
            inpH.value = '';
        }

        recalculateModalTotals();
    }

    // Botones del Modal de Edición
    $('#btn-modal-add-row').on('click', () => {
        const tr = createModalMovementRow();
        tr.querySelector('.modal-input-codigo')?.focus();
    });

    //btn auto cuadrar
    $('#btn-modal-auto-balance').on('click', autoBalanceModal);

    /**
     * Recopilar datos del modal para guardar
     */
    function getModalAsientoData() {
        const rows = tbodyModalMovements.querySelectorAll('tr');
        const movimientos = [];

        rows.forEach(r => {
            const codigo = r.querySelector('.modal-input-codigo')?.value.trim() || '';
            const nombre = r.querySelector('.modal-input-nombre')?.value.trim() || '';
            const glosa = r.querySelector('.modal-input-glosa')?.value.trim() || '';
            const debe = parseMoney(r.querySelector('.modal-input-debe')?.value);
            const haber = parseMoney(r.querySelector('.modal-input-haber')?.value);
            const cuentaId = r.querySelector('.input-cuenta-id')?.value || '';
            const movId = r.querySelector('.input-cuenta-id')?.dataset.movId || '';

            if (codigo || debe > 0 || haber > 0) {
                movimientos.push({
                    num_cuenta: codigo,
                    nombre_cuenta: nombre,
                    description: glosa,
                    debit: debe,
                    credit: haber,
                    account: Number(cuentaId),
                    mov_id: movId
                });
            }
        });

        let totalDebe = 0;
        let totalHaber = 0;
        movimientos.forEach(m => {
            totalDebe += m.debit;
            totalHaber += m.credit;
        });

         //incluir auxiliares a cada movimeinto
        const movimientosAux = movimientos.map(movimiento => {
            //filtrar los auxiliares que pertenecen al movimiento
            const auxiliaresMov = auxiliaresMovimiento.filter(aux => aux.account == movimiento.account && aux.movId == movimiento.mov_id);
            return {
                ...movimiento,
                auxiliares: auxiliaresMov
            };
        });

        return {
            idAsiento: document.getElementById('modal-edit-id').value,
            glosaGeneral: document.getElementById('modal-edit-glosa').value,
            totalDebe: totalDebe,
            totalHaber: totalHaber,
            diferencia: (totalDebe - totalHaber),
            movimientos: movimientosAux,
            auxiliares: auxiliaresMovimiento
        };
    }

    // Contabilizar y guardar cambios desde el modal
    $('#btn-modal-save-post').on('click', () => {
        const data = getModalAsientoData();
        if (data.movimientos.length < 2) {
            Swal.fire({
                icon: 'warning',
                title: 'Debe registrar al menos 2 movimientos.',
            })
            return;
        }
        if (data.diferencia !== 0 || data.totalDebe === 0) {
            Swal.fire({
                icon: 'warning',
                title: 'El asiento debe estar cuadrado para contabilizar.',
            })
            return;
        }

        const missingAcc = data.movimientos.some(m => !m.num_cuenta);
        if (missingAcc) {
            Swal.fire({
                icon: 'warning',
                title: 'Hay líneas con montos pero sin cuenta seleccionada.',
            })
            return;
        }

        if (typeof saveAsientoToStorage === 'function') {
            saveAsientoToStorage(data);
        }
    });

    //GUARDAR CAMBIOS DE ASIENTO
    const saveAsientoToStorage = async(payload) => {
        const result = await Swal.fire({
            title: 'Guardar cambios?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33',
            confirmButtonText: 'Si, Modificar',
            cancelButtonText: 'Cancelar',
            showLoaderOnConfirm: true,
            allowOutsideClick: () => !Swal.isLoading(),
            preConfirm: async () => {
                Swal.update({
                    title: 'Guardando cambios...',
                    text: 'Por favor espere'
                })

                try {
                    const response = await fetch(`/contabilidad/asientos_contables/update/${parseInt(payload.idAsiento)}/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': "application/json",
                            'X-CSRFToken': csrftoken,
                            'X-App-Request': 'true'
                        },
                        body: JSON.stringify(payload)
                    });

                    const data = await response.json();
                    console.log(data)

                    if (!data.success) {
                        const mensajeError = data.message || data.error || 'Ocurrió un error inesperado al guardar.';
                        Swal.showValidationMessage(mensajeError);
                        return false;
                    }
                    

                    return data;

                } catch (error) {
                    console.error(error);
                    Swal.showValidationMessage(`Error: ${error.message}`);
                }
            }
        });

        if (result.isConfirmed && result.value.success) {
            modalEdit.hide();
            auxiliaresMovimiento = [];
            Swal.fire({
                icon: 'success',
                title: '¡Operación Exitosa!',
                text: result.value.message || 'Asiento contable actualizado correctamente.',
                showConfirmButton: true,
                confirmButtonText: 'Refrescar y continuar',
                confirmButtonColor: '#3085d6',
                allowOutsideClick: false, // Obliga al usuario a interactuar con el botón
                allowEscapeKey: false     // Evita cerrar con la tecla Escape
            }).then((confirmResult) => {
                if (confirmResult.isConfirmed) {
                    // Se ejecuta únicamente cuando el usuario presiona "Refrescar y continuar"
                    getAsientosFromStorage();
                }
            });
            
        }
    }

    // =========================================================================
    // MODAL DE CATÁLOGO DE CUENTAS (PARA EDICIÓN RÁPIDA)
    // =========================================================================
    function openAccountsCatalogModal() {
        if (inputSearchAccDt) inputSearchAccDt.value = '';
        renderAccountsCatalog(typeof CATALOGO_CUENTAS !== 'undefined' ? CATALOGO_CUENTAS : []);
        modalAccounts.show();
        setTimeout(() => inputSearchAccDt?.focus(), 300);
    }

    function renderAccountsCatalog(list) {
        if (!tbodyAccountsDt) return;
        tbodyAccountsDt.innerHTML = '';

        list.forEach(acc => {
            const tr = document.createElement('tr');
            tr.className = 'account-item-selectable';
            tr.innerHTML = `
                <td class="fw-bold font-monospace text-primary">${acc.num_cuenta}</td>
                <td>${acc.nombre}</td>
                <td class="text-center">
                    <span class="badge ${acc.is_auxiliar === true ? 'bg-primary' : 'bg-secondary'}">
                        ${acc.is_auxiliar === true ? 'Si' : 'No'}
                    </span>
                </td>
                <td class="text-center">
                    <span class="badge ${acc.tratamiento_especial === true ? 'bg-primary' : 'bg-secondary'}">
                        ${acc.tratamiento_especial === true ? 'Si' : 'No'}
                    </span>
                </td>
            `;

            tr.addEventListener('click', () => {
                if (activeEditRowId) {
                    const row = document.querySelector(`tr[data-modal-row-id="${activeEditRowId}"]`);
                    if (row) {
                        const inpCod = row.querySelector('.modal-input-codigo');
                        const inpNom = row.querySelector('.modal-input-nombre');
                        const inpCuentaId = row.querySelector('.input-cuenta-id');
                        if (inpCod) {
                            inpCod.value = acc.num_cuenta;
                            inpCod.classList.remove('is-invalid');
                            inpCod.classList.add('is-valid');
                            inpCuentaId.value = acc.id;

                        }
                        if (inpNom) inpNom.value = acc.nombre;
                    }
                }
                modalAccounts.hide();
            });

            tbodyAccountsDt.appendChild(tr);
        });
    }

    if (inputSearchAccDt) {
        inputSearchAccDt.addEventListener('input', (e) => {
            if (typeof buscarCuentas === 'function') {
                const filtered = buscarCuentas(e.target.value);
                renderAccountsCatalog(filtered);
            }
        });
    }

        /**
     * Buscar cuentas por término (código o nombre)
     */
    function buscarCuentas(query) {
        if (!query) return CATALOGO_CUENTAS;
        const q = query.toLowerCase().trim();
        return CATALOGO_CUENTAS.filter(c => 
            c.num_cuenta.toLowerCase().includes(q) || 
            c.nombre.toLowerCase().includes(q) 
        );
    }

    /**
     * Obtener cuenta por código exacto
     */
    function obtenerCuentaPorCodigo(num_cuenta) {
        return CATALOGO_CUENTAS.find(c => c.num_cuenta === num_cuenta) || null;
    }

    // =========================================================================
    // FILTROS RÁPIDOS DE DATATABLES
    // =========================================================================


    // Datalist de cuentas para autocompletado en el modal
    const datalistDt = document.getElementById('list-cuentas');
    if (datalistDt && typeof CATALOGO_CUENTAS !== 'undefined') {
        CATALOGO_CUENTAS.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.num_cuenta;
            opt.textContent = `${c.num_cuenta} - ${c.nombre}`;
            datalistDt.appendChild(opt);
        });
    }

    // Inicializar carga de asientos
    getAsientosFromStorage();

    //SOLICITUDES

    // solicitudes

    // busqueda de auxiliares
    let timerBusquedaPersona = null;
    const inputBuscarPersona = document.getElementById('search-auxiliar-modal');
    const resultSearchPersona = document.getElementById('result-search-aux');
    const personaSeleccionada = document.getElementById("persona-seleccionada");
    let auxiliaresMovimiento = [];

    inputBuscarPersona.addEventListener('input', () => {
        clearTimeout(timerBusquedaPersona);

        const search = inputBuscarPersona.value.trim();
        resultSearchPersona.innerHTML = '';

        if(search.length <2) return

        timerBusquedaPersona = setTimeout(() => {
            buscarAuxuliares(search)
        }, 300)
    })

    //realizar peticion de busqueda
    const buscarAuxuliares = async (search) => {
        try{
            resultSearchPersona.innerHTML = `
            <div class="list-group-item text-muted>
                Buscando...
            </div>`

            const response = await fetch(`/contabilidad/asientos_contables/buscar_persona/?q=${encodeURIComponent(search)}`, 
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

            if(!data.success) {
                throw new Error(data.message || 'No es posible obtener los auxiliares')
            }

            mostrarResultadoAuxiliares(data.data)
        } catch (error){
            console.error(error)
            resultSearchPersona.innerHTML = `
            <div class="list-group-item text-danger>
                ${error.message || 'No es posible obtener los auxiliares'}
            </div>`
        }
    }

    //mostrar listado de auxiliares
    const mostrarResultadoAuxiliares = (data) => {
        resultSearchPersona.innerHTML = '';

        if(data.length === 0){
            const item = document.createElement("div")
            item.className = "list-group-item list-group-item-action text-muted text-center"
            item.innerHTML = `Sin resultados`
            resultSearchPersona.appendChild(item)
            return
        }

        data.forEach(row => {
            const item = document.createElement("button")
            item.type = "button"
            item.className = "list-group-item list-group-item-action resultado-persona"
            item.dataset.personId = row.id
            item.dataset.personRut = row.rut
            item.dataset.personNombre = row.nombre
            item.innerHTML = `
                <div class="fw-semibold">
                    ${row.nombre}
                </div>
                <small class="text-muted">
                    RUT: ${row.rut}
                    ${row.person_type}
                </small>
            `
            resultSearchPersona.appendChild(item)
        })
    }

    //seleccionar auxiliar
    resultSearchPersona.addEventListener("click", (e) => {
        const seleccion = e.target.closest(".resultado-persona")

        if (!seleccion) return

        const personId = seleccion.dataset.personId
        const personRut = seleccion.dataset.personRut
        const personNombre = seleccion.dataset.personNombre

        //guardar seleccion en input hidden
        personaSeleccionada.value = personId

        inputBuscarPersona.value = personNombre

        inputBuscarPersona.dataset.nombre = personNombre
        inputBuscarPersona.dataset.rut = personRut
        inputBuscarPersona.dataset.personId = personId

        resultSearchPersona.innerHTML = ''
        resultSearchPersona.classList.remove('show')
    })

    //capturar el click agregar auxiliar modal
    document.addEventListener("click", (e) => {
        if (e.target && e.target.closest("#btn-add-auxiliar")){
            e.preventDefault();
            const montoAux = document.getElementById("monto-auxiliar-modal").value;
            const idPerson = inputBuscarPersona.dataset.personId;
            const rutPerson = inputBuscarPersona.dataset.rut;
            const nombrePerson = inputBuscarPersona.dataset.nombre;
            const cuentaMov = document.getElementById("cuenta-seleccionada-modal").value;
            const movId = document.getElementById("cuenta-seleccionada-modal").dataset.movId;

            let montoLimpio = montoAux.replaceAll(".", "").replaceAll("$", "");
            montoLimpio = parseInt(montoLimpio, 10);

            if (!montoAux || !idPerson || !rutPerson || !nombrePerson) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Debe seleccionar un auxiliar y ingresar un monto',
                })
                return;
            }

            if (montoAux <= 0) {
                Swal.fire({
                    icon: 'warning',
                    title: 'El monto debe ser mayor a 0',
                })
                return;
            }

            // Evitar persona repetida
            const existe = auxiliaresMovimiento.some(
                auxiliar => auxiliar.id === Number(idPerson) && auxiliar.cuenta === Number(cuentaMov)
            );

            if (existe) {
                Swal.fire({
                    icon: "warning",
                    title: "Persona ya agregada",
                    text: "La persona seleccionada ya existe en los auxiliares."
                });

                return;
            }

            auxiliaresMovimiento.push({
                person: Number(idPerson),
                rut: rutPerson,
                nombre: nombrePerson,
                amount: montoLimpio,
                account: Number(cuentaMov),
                movId : movId
            });

            //limpiar seleccion aux
            inputBuscarPersona.value = "";
            inputBuscarPersona.dataset.personId = "";
            inputBuscarPersona.dataset.rut = "";
            inputBuscarPersona.dataset.nombre = "";
            personaSeleccionada.value = "";
            resultSearchPersona.innerHTML = '';
            resultSearchPersona.classList.remove('show');

            // Limpiar monto
            document.getElementById("monto-auxiliar-modal").value = '';

            // actualizar tabla
            renderizarTblAux();
            
        }
    })

    //tabla auxiliares modal
    const renderizarTblAux = () => {
        const tblBodyAux = document.getElementById("tbody-auxiliares-modal");
        const cuentaMov = document.getElementById("cuenta-seleccionada-modal").value;
        const movId = document.getElementById("cuenta-seleccionada-modal").dataset.movId;
        tblBodyAux.innerHTML = '';
        auxiliaresMovimiento.forEach((auxiliar, index) => {
            if(auxiliar.account === Number(cuentaMov) && auxiliar.movId == movId) {
                let montoFormat = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' }).format(auxiliar.amount);
                const btnEliminarAux =  `<button type="button" class="btn btn-sm btn-outline-danger btn-eliminar-aux" data-index="${index}">
                <i class="bi bi-trash"></i>
                </button>`;
            
                tblBodyAux.innerHTML += `
                <tr>
                    <td>${auxiliar.rut}</td>
                    <td>${auxiliar.nombre}</td>
                    <td>${montoFormat}</td>
                    <td>${btnEliminarAux}</td>
                </tr>
                `;
            }
        });
    }

    //eliminar aux de tbl
    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".btn-eliminar-aux");
        if (!btn) return;

        const index = parseInt(btn.dataset.index, 10);
        auxiliaresMovimiento.splice(index, 1);
        renderizarTblAux();
    })



});
