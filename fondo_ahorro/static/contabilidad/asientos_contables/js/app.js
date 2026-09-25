//capturar el crftoken para las solicitudes
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

document.addEventListener('DOMContentLoaded', () => {
    // Estado de la aplicación
    let activeRowIndexForAccount = null;
    let nextRowId = 1;

    // Elementos del DOM
    const tbodyMovements = document.getElementById('tbody-movements');
    const btnAddRow = document.getElementById('btn-add-row');
    const btnAutoBalance = document.getElementById('btn-auto-balance');
    const btnClearAll = document.getElementById('btn-clear-all');
    const btnPostEntry = document.getElementById('btn-post-entry');

    // Totales y estado
    const totalDebeEl = document.getElementById('total-debe');
    const totalHaberEl = document.getElementById('total-haber');
    const totalDiferenciaEl = document.getElementById('total-diferencia');
    const badgeStatusBalance = document.getElementById('badge-status-balance');
    const badgeStatusCard = document.getElementById('balance-status-card');
    const countRowsEl = document.getElementById('count-rows');

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
     * Limpiar formato de moneda a número float
     */
    function parseMoney(val) {
        if (!val) return 0;
        if (typeof val === 'number') return isNaN(val) ? 0 : Math.round(val);
        
        // Remueve el símbolo $, puntos de miles, espacios y cualquier carácter no numérico excepto el signo menos (-)
        const cleaned = val.toString().replace(/[^0-9-]/g, '');
        const parsed = parseInt(cleaned, 10);
        
        return isNaN(parsed) ? 0 : parsed;
    }

    /**
     * Crear una nueva fila de movimiento contable
     */
    function createMovementRow(data = {}) {
        const rowId = nextRowId++;
        const tr = document.createElement('tr');
        tr.className = 'movement-row';
        tr.id = `row-${rowId}`;
        tr.dataset.rowId = rowId;

        const defaultGlosa = data.glosa || document.getElementById('glosa-general')?.value || '';
        const defaultDebe = data.debe !== undefined ? data.debe : 0;
        const defaultHaber = data.haber !== undefined ? data.haber : 0;
        const defaultCodigoCuenta = data.codigoCuenta || '';

        // Buscar info de la cuenta
        let accountName = "Seleccione o busque una cuenta...";
        if (defaultCodigoCuenta) {
            const acc = obtenerCuentaPorCodigo(defaultCodigoCuenta);
            if (acc) accountName = acc.nombre;
        }

        tr.innerHTML = `
            <td class="text-center align-middle" style="width: 45px;">
                <span class="badge bg-light text-secondary border row-number">0</span>
            </td>
            <td style="min-width: 250px; max-width: 320px;">
                <div class="input-group input-group-sm input-account-group">
                    <button class="btn btn-outline-secondary btn-search-account" type="button" title="Buscar en catálogo (F2)">
                        <i class="bi bi-search"></i>
                    </button>
                    <input type="text" class="form-control form-control-sm input-codigo-cuenta" 
                           placeholder="Numero de cuenta" value="${defaultCodigoCuenta}" 
                           list="list-cuentas" maxlength="15" autocomplete="off" style="max-width: 150px; font-weight: 600;">
                    <input type="text" class="form-control form-control-sm input-nombre-cuenta bg-light" 
                           placeholder="Nombre de cuenta" value="${accountName !== 'Seleccione o busque una cuenta...' ? accountName : ''}" readonly>
                    <input type="hidden" class="input-cuenta-id">
                </div>
            </td>
            <td style="min-width: 200px;">
                <input type="text" class="form-control form-control-sm input-glosa-linea" 
                       placeholder="Detalle del movimiento" value="${defaultGlosa}">
            </td>
            <td style="width: 140px;">
                <div class="input-group input-group-sm">
                    <span class="input-group-text bg-light text-primary border-end-0 py-0 px-2 fw-semibold">$</span>
                    <input type="text" class="form-control form-control-sm input-currency input-debe border-start-0" 
                           placeholder="0" value="${defaultDebe > 0 ? formatMoney(defaultDebe) : ''}">
                </div>
            </td>
            <td style="width: 140px;">
                <div class="input-group input-group-sm">
                    <span class="input-group-text bg-light text-success border-end-0 py-0 px-2 fw-semibold">$</span>
                    <input type="text" class="form-control form-control-sm input-currency input-haber border-start-0" 
                           placeholder="0" value="${defaultHaber > 0 ? formatMoney(defaultHaber) : ''}">
                </div>
            </td>
            <td class="text-center align-middle row-actions-column" style="width: 90px;">
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary btn-auxiliar-row" type="button" title="Agregar auxiliar" disabled>
                        <i class="bi bi-person"></i>
                    </button>
                    <button class="btn btn-outline-danger btn-delete-row" type="button" title="Eliminar línea">
                        <i class="bi bi-trash3"></i>
                    </button>
                </div>
            </td>
        `;

        setupRowEvents(tr);
        tbodyMovements.appendChild(tr);
        renumberRows();
        recalculateTotals();

        return tr;
    }

    /**
     * Configurar eventos interactivos para una fila
     */
    function setupRowEvents(tr) {
        const inputCodigo = tr.querySelector('.input-codigo-cuenta');
        const inputNombre = tr.querySelector('.input-nombre-cuenta');
        const inputCuentaId = tr.querySelector('.input-cuenta-id');
        const btnSearch = tr.querySelector('.btn-search-account');
        const inputDebe = tr.querySelector('.input-debe');
        const inputHaber = tr.querySelector('.input-haber');
        const btnDelete = tr.querySelector('.btn-delete-row');
        const btnAux = tr.querySelector('.btn-auxiliar-row');

        // Búsqueda modal
        btnSearch.addEventListener('click', () => {
            activeRowIndexForAccount = tr.dataset.rowId;
            openAccountsModal();
        });

        // Cambio directo en código de cuenta
        inputCodigo.addEventListener('input', () => {
            const code = inputCodigo.value.trim();
            const account = obtenerCuentaPorCodigo(code);
            if (account) {
                inputNombre.value = account.nombre;
                inputCuentaId.value = account.id;
                inputCodigo.classList.remove('is-invalid');
                inputCodigo.classList.add('is-valid');
                btnAux.disabled = (account.is_auxiliar == true) ? false : true;
            } else {
                inputNombre.value = '';
                inputCuentaId.value = '';
                inputCodigo.classList.remove('is-valid');
                btnAux.disabled = true;
                if (code.length >= 3) {
                    inputCodigo.classList.add('is-invalid');
                } else {
                    inputCodigo.classList.remove('is-invalid');
                }
            }
        });

        // Formato y validación Debe
        inputDebe.addEventListener('focus', (e) => {
            const val = parseMoney(e.target.value);
            if (val === 0) e.target.value = '';
            else e.target.value = val;
            tr.classList.add('row-active');
        });

        inputDebe.addEventListener('blur', (e) => {
            tr.classList.remove('row-active');
            const val = parseMoney(e.target.value);
            if (val > 0) {
                e.target.value = formatMoney(val);
                // Si ingresa Debe, opcionalmente vaciar Haber para evitar ambigüedad
                inputHaber.value = '';
            } else {
                e.target.value = '';
            }
            recalculateTotals();
        });

        inputDebe.addEventListener('keyup', (e) => {
            if (e.key === 'Enter') {
                inputHaber.focus();
            }
            recalculateTotals();
        });

        // Formato y validación Haber
        inputHaber.addEventListener('focus', (e) => {
            const val = parseMoney(e.target.value);
            if (val === 0) e.target.value = '';
            else e.target.value = val;
            tr.classList.add('row-active');
        });

        inputHaber.addEventListener('blur', (e) => {
            tr.classList.remove('row-active');
            const val = parseMoney(e.target.value);
            if (val > 0) {
                e.target.value = formatMoney(val);
                // Si ingresa Haber, vaciar Debe
                inputDebe.value = '';
            } else {
                e.target.value = '';
            }
            recalculateTotals();
        });

        inputHaber.addEventListener('keyup', (e) => {
            if (e.key === 'Enter') {
                // Si presiona enter en la última columna, crear una nueva fila
                const nextRow = tr.nextElementSibling;
                if (!nextRow) {
                    const newTr = createMovementRow();
                    const nextInput = newTr.querySelector('.input-codigo-cuenta');
                    if (nextInput) nextInput.focus();
                } else {
                    const nextInput = nextRow.querySelector('.input-codigo-cuenta');
                    if (nextInput) nextInput.focus();
                }
            }
            recalculateTotals();
        });

        // Eliminar fila
        btnDelete.addEventListener('click', () => {
            tr.remove();
            //quitar los auxiliares de la fila eliminada
            auxiliaresMovimiento = auxiliaresMovimiento.filter(auxiliar => auxiliar.account !== Number(inputCuentaId.value));
            renumberRows();
            recalculateTotals();
            Swal.fire('Fila eliminada', 'La fila se ha eliminado correctamente.', 'success');
        });

        // Abrir modal de auxiliares
        btnAux.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById("cuenta-seleccionada-modal").value = inputCuentaId.value;
            renderizarTblAux();
            $('#modal-auxiliares').modal('show');
        });
    }

    /**
     * Abrir modal de cuentas
     */
    function openAccountsModal() {
        modalAccounts.show();
    }

    /**
     * Renumerar filas en la tabla
     */
    function renumberRows() {
        const rows = tbodyMovements.querySelectorAll('tr');
        rows.forEach((row, index) => {
            const badge = row.querySelector('.row-number');
            if (badge) badge.textContent = index + 1;
        });
        if (countRowsEl) countRowsEl.textContent = rows.length;
    }

    /**
     * Recalcular totales de Debe, Haber y Diferencia
     */
    function recalculateTotals() {
        let sumDebe = 0;
        let sumHaber = 0;

        const rows = tbodyMovements.querySelectorAll('tr');
        rows.forEach(row => {
            const debeVal = parseMoney(row.querySelector('.input-debe')?.value);
            const haberVal = parseMoney(row.querySelector('.input-haber')?.value);
            sumDebe += debeVal;
            sumHaber += haberVal;
        });

        const diff = sumDebe - sumHaber;
        // Actualizar valores en UI
        if (totalDebeEl) totalDebeEl.textContent = formatMoney(sumDebe);
        if (totalHaberEl) totalHaberEl.textContent = formatMoney(sumHaber);
        if (totalDiferenciaEl) totalDiferenciaEl.textContent = formatMoney(diff);
        // Actualizar badges e indicadores de balance
        if (sumDebe === 0 && sumHaber === 0) {
            badgeStatusBalance.className = "status-pill bg-secondary text-white";
            badgeStatusBalance.innerHTML = `<i class="bi bi-circle"></i> SIN MOVIMIENTOS`;
            if (badgeStatusCard) {
                badgeStatusCard.className = "balance-card bg-light text-secondary";
            }
            if (btnPostEntry) btnPostEntry.disabled = true;
        } else if (diff === 0) {
            badgeStatusBalance.className = "status-pill balanced";
            badgeStatusBalance.innerHTML = `<i class="bi bi-check-circle-fill"></i> ASIENTO CUADRADO`;
            if (badgeStatusCard) {
                badgeStatusCard.className = "balance-card balance-status-balanced";
            }
            if (btnPostEntry) btnPostEntry.disabled = false;
        } else {
            const diffFormatted = formatMoney(Math.abs(diff));
            const msg = diff > 0 ? `DEBE SUPERA EN $ ${diffFormatted}` : `HABER SUPERA EN $ ${diffFormatted}`;
            badgeStatusBalance.className = "status-pill unbalanced";
            badgeStatusBalance.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i> DESCUADRADO (${msg})`;
            if (badgeStatusCard) {
                badgeStatusCard.className = "balance-card balance-status-unbalanced";
            }
            if (btnPostEntry) btnPostEntry.disabled = true;
        }
    }

    /**
     * Auto-cuadre inteligente de la partida doble
     */
    function autoBalance() {
        let sumDebe = 0;
        let sumHaber = 0;

        const rows = Array.from(tbodyMovements.querySelectorAll('tr'));
        rows.forEach(row => {
            sumDebe += parseMoney(row.querySelector('.input-debe')?.value);
            sumHaber += parseMoney(row.querySelector('.input-haber')?.value);
        });

        const diff = sumDebe - sumHaber;

        if (diff === 0) {
            Swal.fire('Asiento perfectamente cuadrado', 'El asiento ya estaba perfectamente cuadrado.', 'info');
            return;
        }

        const absDiff = diff

        // Buscar una fila vacía o con monto 0 para asignarle el cuadre
        let targetRow = rows.find(r => {
            const d = parseMoney(r.querySelector('.input-debe')?.value);
            const h = parseMoney(r.querySelector('.input-haber')?.value);
            return d === 0 && h === 0;
        });

        // Si no hay fila vacía, crear una nueva
        if (!targetRow) {
            targetRow = createMovementRow();
        }

        const inputDebe = targetRow.querySelector('.input-debe');
        const inputHaber = targetRow.querySelector('.input-haber');

        if (diff > 0) {
            // Debe es mayor -> Falta en el Haber
            inputHaber.value = formatMoney(absDiff);
            inputDebe.value = '';
            // showToast(`Se asignó $ ${formatMoney(absDiff)} al HABER para cuadrar.`, "success");
        } else {
            // Haber es mayor -> Falta en el Debe
            inputDebe.value = formatMoney(absDiff);
            inputHaber.value = '';
            // showToast(`Se asignó $ ${formatMoney(absDiff)} al DEBE para cuadrar.`, "success");
        }

        recalculateTotals();
        targetRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    /**
     * Modal del Plan de Cuentas
     */
    const modalAccounts = new bootstrap.Modal(document.getElementById('modal-accounts'));
    const inputSearchAccountModal = document.getElementById('search-account-modal');
    const tableAccountsBody = document.getElementById('tbody-accounts-catalog');

    function openAccountsModal() {
        if (inputSearchAccountModal) inputSearchAccountModal.value = '';
        renderAccountsTable(CATALOGO_CUENTAS);
        modalAccounts.show();
        setTimeout(() => {
            if (inputSearchAccountModal) inputSearchAccountModal.focus();
        }, 300);
    }

    function renderAccountsTable(accountsList) {
        if (!tableAccountsBody) return;
        tableAccountsBody.innerHTML = '';

        if (accountsList.length === 0) {
            tableAccountsBody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center text-muted py-4">
                        <i class="bi bi-search fs-3 d-block mb-2"></i>
                        No se encontraron cuentas que coincidan con la búsqueda.
                    </td>
                </tr>
            `;
            return;
        }

        accountsList.forEach(acc => {
            const tr = document.createElement('tr');
            tr.className = 'account-item-selectable';
            tr.innerHTML = `
                <td class="fw-bold text-primary" style="">${acc.num_cuenta}</td>
                <td style="">${acc.nombre}</td>
                <td>
                    <span class="badge ${acc.is_auxiliar == true ? 'bg-primary' : 'bg-secondary'}">
                        ${acc.is_auxiliar == true ? 'Si' : 'No'}
                    </span>
                </td>
                <td class="text-center" style="">
                    <span class="badge ${acc.is_tratamiento_especial == true ? 'bg-primary' : 'bg-secondary'}">
                         ${acc.is_tratamiento_especial == true ? 'Si' : 'No'}
                    </span>
                </td>
            `;

            tr.addEventListener('click', () => {
                selectAccountForActiveRow(acc);
            });

            tableAccountsBody.appendChild(tr);
        });
    }

    if (inputSearchAccountModal) {
        inputSearchAccountModal.addEventListener('input', (e) => {
            const filtered = buscarCuentas(e.target.value);
            renderAccountsTable(filtered);
        });
    }

    function selectAccountForActiveRow(acc) {
        if (activeRowIndexForAccount) {
            
            const row = document.getElementById(`row-${activeRowIndexForAccount}`);
            if (row) {
                const inputCodigo = row.querySelector('.input-codigo-cuenta');
                const inputNombre = row.querySelector('.input-nombre-cuenta');
                const inputCuentaId = row.querySelector('.input-cuenta-id');
                const btnAux = row.querySelector('.btn-auxiliar-row');
                if (inputCodigo) {
                    inputCodigo.value = acc.num_cuenta;
                    inputCodigo.classList.remove('is-invalid');
                    inputCodigo.classList.add('is-valid');
                    btnAux.disabled = (acc.is_auxiliar == true) ? false : true;
                }
                if (inputNombre) {
                    inputNombre.value = acc.nombre;
                }
                if (inputCuentaId) {
                    inputCuentaId.value = acc.id;
                }
            }
        }
        modalAccounts.hide();
    }

    /**
     * Recopilar objeto de datos completo del asiento
     */
    function getJournalEntryData() {
        const rows = tbodyMovements.querySelectorAll('tr');
        const movimientos = [];

        rows.forEach(row => {
            const codigo = row.querySelector('.input-codigo-cuenta')?.value || '';
            const nombre = row.querySelector('.input-nombre-cuenta')?.value || '';
            const glosa = row.querySelector('.input-glosa-linea')?.value || '';
            const debe = parseMoney(row.querySelector('.input-debe')?.value);
            const haber = parseMoney(row.querySelector('.input-haber')?.value);
            const cuentaId = row.querySelector('.input-cuenta-id')?.value || '';

            if (codigo || debe > 0 || haber > 0) {
                movimientos.push({
                    num_cuenta: codigo,
                    nombre_cuenta: nombre,
                    description: glosa,
                    debit: debe,
                    credit: haber,
                    account: Number(cuentaId)
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
            const auxiliaresMov = auxiliaresMovimiento.filter(aux => aux.account == movimiento.account);
            return {
                ...movimiento,
                auxiliares: auxiliaresMov
            };
        });

        return {
            fechaAsiento: document.getElementById('fecha-asiento')?.value || '',
            fechaContable: document.getElementById('fecha-contable')?.value || '',
            periodo: document.getElementById('periodo-asiento')?.value || '',
            tipoAsiento: Number(document.getElementById('tipo-asiento')?.value) || 0,
            glosaGeneral: document.getElementById('glosa-general')?.value || '',
            totalDebe: totalDebe,
            totalHaber: totalHaber,
            diferencia: totalDebe - totalHaber,
            movimientos: movimientosAux,
            auxiliares : auxiliaresMovimiento
        };
    }

    if (btnPostEntry) {
        btnPostEntry.addEventListener('click', () => {
            const data = getJournalEntryData();
            console.log(data)
            if (data.fechaAsiento === '') {
                Swal.fire({
                    icon: 'warning',
                    title: 'Asiento incompleto',
                    text: 'El asiento debe tener una fecha de asiento.',
                })
                return;
            }
            if (data.glosaGeneral === '') {
                Swal.fire({
                    icon: 'warning',
                    title: 'Asiento incompleto',
                    text: 'El asiento debe tener una glosa general.',
                })
                return;
            }
            if (data.movimientos.length < 2) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Asiento incompleto',
                    text: 'El asiento debe tener al menos 2 movimientos.',
                })
                return;
            }
            if (data.diferencia !== 0 || data.totalDebe === 0) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Asiento incompleto',
                    text: 'El asiento debe estar perfectamente cuadrado y con montos mayores a cero.',
                })
                return;
            }

            // Validar cuentas vacías
            const missingAccount = data.movimientos.some(m => !m.num_cuenta);
            if (missingAccount) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Asiento incompleto',
                    text: 'Existen líneas sin cuenta contable especificada.',
                })
                return;
            }
            Swal.fire({
                icon: 'question',
                title: 'Finalizar asiento',
                text: 'Está seguro de que desea finalizar el asiento?',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Si, Finalizar',
                cancelButtonText: 'Cancelar',
            }).then((result) => {
                if (result.isConfirmed) {
                    //contabilizar
                    contabilizar(data);
                }
            })
        });
    }

    /**
     * btn limpiar
     */
    if (btnClearAll) {
        btnClearAll.addEventListener('click', () => {
            Swal.fire({
                icon: 'warning',
                title: 'Limpiar asiento',
                text: 'Está seguro de que desea limpiar todos los datos del asiento actual?',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Si, Limpiar',
                cancelButtonText: 'Cancelar',
            }).then((result) => {
                if (result.isConfirmed) {
                    clearAll();
                }
            })
        });
    }

    /**
     * Limpiar todo
     */
    const clearAll = () => {
        tbodyMovements.innerHTML = '';
        document.getElementById('glosa-general').value = 'Ajuste Contable';
        
        recalculateTotals();
        auxiliaresMovimiento = [];
        document.getElementById('fecha-asiento').value = '';
    }

    /**
     * Botones de acción principales
     */
    if (btnAddRow) {
        btnAddRow.addEventListener('click', () => {
            const tr = createMovementRow();
            const inputCodigo = tr.querySelector('.input-codigo-cuenta');
            if (inputCodigo) inputCodigo.focus();
        });
    }

    if (btnAutoBalance) {
        btnAutoBalance.addEventListener('click', autoBalance);
    }

    /**
     * Atajos de teclado para digitadores contables
     */
    document.addEventListener('keydown', (e) => {
        // Alt + N -> Nueva fila
        if (e.altKey && (e.key === 'n' || e.key === 'N')) {
            e.preventDefault();
            const tr = createMovementRow();
            const inputCodigo = tr.querySelector('.input-codigo-cuenta');
            if (inputCodigo) inputCodigo.focus();
        }

        // F8 -> Auto-cuadre
        if (e.key === 'F8') {
            e.preventDefault();
            autoBalance();
        }

        // F2 -> Abrir catálogo de cuentas si estamos en un input
        if (e.key === 'F2') {
            const activeEl = document.activeElement;
            const row = activeEl?.closest('tr.movement-row');
            if (row) {
                e.preventDefault();
                activeRowIndexForAccount = row.dataset.rowId;
                openAccountsModal();
            }
        }
    });

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

    // Inicializar Datalist de cuentas para autocompletado rápido
    const datalistCuentas = document.getElementById('list-cuentas');
    if (datalistCuentas && typeof CATALOGO_CUENTAS !== 'undefined') {
        CATALOGO_CUENTAS.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.num_cuenta;
            opt.textContent = `${c.num_cuenta} - ${c.nombre}`;
            datalistCuentas.appendChild(opt);
        });
    }

    ['change', 'keyup'].forEach(eventName => {
        document.addEventListener(eventName, (e) => {
            if (e.target && e.target.classList.contains('input-currency')) {
                formatMiles(e.target);
            }
        });
    });

    //SOLO NUMEROS ENTEROS
    const formatInt = (input) => {
        input.value = (input.value + '').replace(/[^0-9]/g, '');
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
                account: Number(cuentaMov)
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
        tblBodyAux.innerHTML = '';
        auxiliaresMovimiento.forEach((auxiliar, index) => {
            if(auxiliar.account !== Number(cuentaMov)) return
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
        });
    }

    //eliminar aux de tbl
    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".btn-eliminar-aux");
        if (!btn) return;

        const index = parseInt(btn.dataset.index, 10);
        
        auxiliaresMovimiento.splice(index, 1);
        console.log(auxiliaresMovimiento)
        renderizarTblAux();
    })

    //enviar datos para contabilizar
    const contabilizar = async(data) => {
        // Spinner de carga
        Swal.fire({
            title: "Espere",
            text: "Guardando datos...",
            allowOutsideClick: false,
            showConfirmButton: false,
            willOpen: () => {
                Swal.showLoading();
            },
        });
        try {
            const response = await fetch("/contabilidad/asientos_contables/contabilizar/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrftoken,
                    "X-App-Request": "true",
                },
                body: JSON.stringify(data),
            });

            const res = await response.json();
            console.log(res)
            Swal.fire({
                icon: res.success ? "success" : "warning",
                title: res.message,
                text: res.success ?"NUMERO DE COMPROBANTE: "+ res.data.numero_comprobante : ""
            });

            if(res.success){
                clearAll()
            }
        } catch (error) {
            console.error(error)
            Swal.fire({
                icon: "error",
                title: "No se pudo guardar",
                text: error.message || "No es posible procesar la solicitud",
            })
        }
        
    }




});