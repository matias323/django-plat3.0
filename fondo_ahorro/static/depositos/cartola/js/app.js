/**
 * LÓGICA DE TEMPLATE DE CARTOLA DE MOVIMIENTOS
 *
 */
//capturar el crftoken para las solicitudes
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
document.addEventListener('DOMContentLoaded', () => {
    let timerBusquedaPartner = null;
    const inputBuscarPartner = document.getElementById('input-search-persona');
    const resultSearchPartner = document.getElementById('dropdown-search-results');
    const btnClearSearch = document.getElementById('btn-clear-search');
    const filtroAnio = document.getElementById('filtro-select-anio');
    const filtroTipo = document.getElementById('filtro-select-tipo');
    const filtroCuenta = document.getElementById('filtro-select-cuenta');
    let dataResult = [];
    let SelectedPerson = [];



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
            console.log(data)
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

    const renderizarDropdownResultados = (resultados) => {
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
        SelectedPerson = persona;
        console.log(SelectedPerson);

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
        document.getElementById('perfil-nombre').textContent = persona.nombre;
        document.getElementById('perfil-rut').textContent = formatRUT(persona.rut);
        document.getElementById('perfil-id-socio').textContent = persona.codigo_funcionario;
        document.getElementById('perfil-categoria').textContent = persona.categoria;
        document.getElementById('perfil-grado').textContent = persona.grado;
        document.getElementById('perfil-escalafon').textContent = persona.grado_escalafon;
    }

    //capturar click btn buscar
    document.addEventListener('click', async (e) => {
        if (e.target && e.target.closest('.btn-buscar-movimientos')) {
            e.preventDefault();
            const anio = filtroAnio.options[filtroAnio.selectedIndex].value;
            const tipo = filtroTipo.options[filtroTipo.selectedIndex].value;
            const cuenta = filtroCuenta.options[filtroCuenta.selectedIndex].value;

            if (SelectedPerson.length === 0) {
                Swal.fire({
                    icon: 'warning',
                    title: 'No se ha seleccionado una persona.',
                })
                return;
            }

            const data = await buscarMovimientos(anio, tipo, cuenta, SelectedPerson.id_person);

            renderTablaCartola(data);
        }
    });

    //buscar movimientos
    const buscarMovimientos = async (anio, tipo, cuenta, persona) => {
        try {
            const response = await fetch(`/depositos/cartola/movimientos/`, {
                method: 'POST',
                headers: {
                    'Content-Type': "application/json",
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                },
                body: JSON.stringify({
                    anio,
                    tipo,
                    cuenta,
                    persona,
                })
            })
            const data = await response.json();
            console.log(data)
            return data.data;
        } catch (error) {
            console.error(error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No fue posible buscar los movimientos.',
            })
        }
    }

    /**
     * Renderiza la tabla de movimientos de la cartola
     */
    const renderTablaCartola = (data) => {
        const tbody = document.getElementById('tbody-cartola-movimientos');
        if (!tbody) return;

        // Conteo en badge de encabezado
        const badgeCoincidencias = document.getElementById('badge-total-coincidencias-cartola');
        if (badgeCoincidencias) {
            badgeCoincidencias.textContent = `${data.length} movimiento${data.length === 1 ? '' : 's'}`;
        }

        // Actualizar texto del encabezado con el año
        const labelAnio = document.getElementById('cartola-anio-activo-label');
        if (labelAnio) {
            labelAnio.textContent = `Año ${filtroAnio.options[filtroAnio.selectedIndex].value}`;
        }

        // Actualizar indicador de cuenta activa en encabezados
        const titleCuenta = document.getElementById('cartola-cuenta-nombre-label');
        if (titleCuenta) {
            titleCuenta.textContent = filtroCuenta.options[filtroCuenta.selectedIndex].text;
        }

        // const list = cartolaState.movimientosFiltrados;
        // const start = (cartolaState.paginaActual - 1) * cartolaState.registrosPorPagina;
        // const end = start + cartolaState.registrosPorPagina;
        // const pageItems = list.slice(start, end);

        if (data.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="10" class="text-center py-5 text-muted">
                        <i class="bi bi-file-earmark-x fs-1 d-block mb-2 text-secondary opacity-50"></i>
                        <h6 class="fw-bold text-dark">No se registran movimientos para este filtro</h6>
                        <p class="small mb-0">Modifica el año seleccionado o la cuenta consultada para ver más registros.</p>
                    </td>
                </tr>
            `;
            return;
        }

        

        let html = '';
        data.forEach((m, idx) => {
            // Badges por tipo de cuenta
            let badgeCta = 'bg-primary-subtle text-primary border-primary-subtle';
            let iconoCta = 'bi-bank';
            if (m.contribution_type.id == 2) {
                badgeCta = 'bg-success-subtle text-success border-success-subtle';
                iconoCta = 'bi-house-heart';
            } else if (m.contribution_type.id == 3) {
                badgeCta = 'bg-warning-subtle text-warning border-warning-subtle';
                iconoCta = 'bi-cash-stack';
            }

            // Badges por tipo de movimiento

            let badgeTipo = 'bg-danger text-white';
            let labelTipo = 'Giro / Retiro';

            if(m.movement_type.id == 2){ //deposito
                badgeTipo = 'bg-success text-white';
                labelTipo = 'Abono / Depósito';
            } else if (m.movement_type.id == 3) { //utilidades
                badgeTipo = 'bg-warning text-dark';
                labelTipo = 'Utilidades Ganado';
            } else if (m.movement_type.id == 4) { //reajuste
                badgeTipo = 'bg-info text-white';
                labelTipo = 'Reajuste IPC';
            } else if (m.movement_type.id == 5) { //interes
                badgeTipo = 'bg-info text-white';
                labelTipo = 'Interes Ganado';
            }

            html += `
                <tr>
                    <td class="text-nowrap">
                        <div class="fw-bold text-dark">${m.created_at}</div>

                    </td>
                    <td>
                        <span class="badge ${badgeCta} border fs-xs d-inline-flex align-items-center gap-1">
                            <i class="bi ${iconoCta}"></i>${m.contribution_type.description} - ${m.contribution_type.comment}
                        </span>
                    </td>
                    <td>
                        <span class="badge ${badgeTipo} fs-xs">${labelTipo}</span>
                    </td>
                    <td>
                        <div class="text-dark fw-semibold fs-sm">${m.description}</div>
                    </td>
                    <td class="text-end font-monospace text-danger fw-bold">
                        ${m.movement_type.id == 1 ? `- ${formatMoney(m.amount)}` : '-'}
                    </td>
                    <td class="text-end font-monospace text-success fw-bold">
                        ${m.movement_type.id > 1 ? `+ ${formatMoney(m.amount)}` : '-'}
                    </td>
                    <td class="text-end font-monospace text-dark fw-bold bg-light">
                        ${formatMoney(m.amount)}
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = html;

        // Listeners de modales para cada fila
        // tbody.querySelectorAll('.btn-ver-ticket-op').forEach(btn => {
        //     btn.addEventListener('click', () => {
        //         const opId = btn.getAttribute('data-op');
        //         const mov = cartolaState.todosMovimientosSocio.find(m => m.id === opId);
        //         if (mov) abrirModalTicket(mov);
        //     });
        // });

        // tbody.querySelectorAll('.btn-ver-asiento-op').forEach(btn => {
        //     btn.addEventListener('click', () => {
        //         const opId = btn.getAttribute('data-op');
        //         const mov = cartolaState.todosMovimientosSocio.find(m => m.id === opId);
        //         if (mov) abrirModalAsiento(mov);
        //     });
        // });

        // tbody.querySelectorAll('.btn-print-individual').forEach(btn => {
        //     btn.addEventListener('click', () => {
        //         const opId = btn.getAttribute('data-op');
        //         const mov = cartolaState.todosMovimientosSocio.find(m => m.id === opId);
        //         if (mov) {
        //             abrirModalTicket(mov);
        //             setTimeout(() => window.print(), 300);
        //         }
        //     });
        // });
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






})





