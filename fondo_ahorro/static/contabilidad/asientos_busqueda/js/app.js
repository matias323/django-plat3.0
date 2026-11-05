/**
 * LÓGICA DE LA PLANTILLA DE BUSQUEDA DE ASIENTOS CONSTABLES
 *
 */
//capturar el crftoken para las solicitudes
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

document.addEventListener('DOMContentLoaded', () => {
    let asientosData = [];
    let dataTableInstance = null;
    let dataTableViewAux = null;

    //inputs de busqueda
    const filterNum = document.getElementById('filter-num');
    const filterPeriodo = document.getElementById('filter-periodo');
    const filterTipo = document.getElementById('filter-tipo');
    const filterEstado = document.getElementById('filter-estado');
    const filterFechaDesde = document.getElementById('filter-fecha-desde');
    const filterFechaHasta = document.getElementById('filter-fecha-hasta');

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
     * Formatear número a moneda (0 decimales)
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
     * Renderizador de Subfilas (Child Rows) en DataTables para ver detalle de movimientos
     */
    function formatChildRow(asiento) {
        let movRows = '';
        let totalDebe = 0;
        let totalHaber = 0;
        let is_auxiliar = false;
        let btn_aux = '';
        if (asiento.is_null) {
            movRows =`
                <tr>
                    <td colspan="8" class="text-center text-muted"><span class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i>Asiento contable NULO</span></td>
                </tr>
            `;
        }

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
                    <td class="text-muted" style="width: 130px;">${m.refDoc || '-'}</td>
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
                                <th>Doc. Ref.</th>
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
                                <td colspan="6" class="text-end text-uppercase">Sumas del Asiento:</td>
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
            const idAsiento = Number(e.target.dataset.asiento);
            const idMovimiento = Number(e.target.dataset.id);

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

    // initDataTable();

    //inicar dataTables
    function initDataTable() {

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

                        if (row.aprobacion) {
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


    /**
     * Limpiar filtros
     */
    document.addEventListener('click', (e) => {
        if (e.target && e.target.closest('#btn-clear-filters')) {
            e.preventDefault();
            if (filterNum) filterNum.value = '';
            if (filterPeriodo) filterPeriodo.value= 0;
            if (filterTipo) filterTipo.value = 0;
            if (filterEstado) filterEstado.value = 0;
            if (filterFechaDesde) filterFechaDesde.value = '';
            if (filterFechaHasta) filterFechaHasta.value = '';
            asientosData = [];
            if ($.fn.DataTable.isDataTable('#tabla-asientos-dt')) {
                $('#tabla-asientos-dt').DataTable().clear().draw();
            } 
        }
    });

    //capturar click buscar
    document.addEventListener('click', async (e) => {
        if(e.target && e.target.closest('#btn-search')) {
            e.preventDefault();
            Swal.showLoading();
            const num = filterNum.value.trim() ? parseInt(filterNum.value.trim()) : 0;
            const periodo = filterPeriodo.options[filterPeriodo.selectedIndex].value;
            const tipo = filterTipo.options[filterTipo.selectedIndex].value;
            const estado = filterEstado.options[filterEstado.selectedIndex].value;
            const fechaDesde = filterFechaDesde.value.trim();
            const fechaHasta = filterFechaHasta.value.trim();

            asientosData = await buscarAsientos(num, periodo, tipo, estado, fechaDesde, fechaHasta);
            initDataTable();
            Swal.close();
            if (asientosData.length === 0) {
                Swal.fire({
                    icon: 'warning',
                    title: 'No se encontraron asientos.',
                })
            }
        }
    }) 

    const buscarAsientos = async (num, periodo, tipo, estado, fechaDesde, fechaHasta) => {
        try {
            const response = await fetch(`/contabilidad/asientos_contables/busqueda/buscar/`, {
                method: 'POST',
                headers: {
                    'Content-Type': "application/json",
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                },
                body: JSON.stringify({
                    num,
                    periodo,
                    tipo,
                    estado,
                    fechaDesde,
                    fechaHasta
                })
            })
            const data = await response.json();
            return data.data;
        } catch (error) {
            console.error(error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No fue posible buscar los asientos.',
            })
            return [];
        }
    }


    // Formatea el valor al detectar un cambio o cuando se escribe
    ['change', 'keyup'].forEach((eventType) => {
        document.addEventListener(eventType, (e) => {
            if (e.target && e.target.closest('.input-int')) {
                formatInt(e.target);
            }
        });
    });

    //SOLO NUMEROS ENTEROS
    const formatInt = (input) => {
        input.value = (input.value + '').replace(/[^0-9]/g, '');
    }

});

