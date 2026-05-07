/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

/**
 * Manufacturing Dashboard - Dashboard Principal para Managers
 * Muestra resumen de órdenes de manufactura con alertas en tiempo real
 */
export class ManufacturingDashboard extends Component {
    setup() {
        // Servicios de Odoo
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        // Estado reactivo del componente
        this.state = useState({
            loading: true,
            data: null,
            lastUpdate: null,
            autoRefresh: true,
            refreshInterval: 30, // segundos
            activeFilter: null, // Nuevo: filtro activo (Laboratory, Production, etc.)
            orderList: [],      // Nuevo: lista de órdenes filtradas
            loadingList: false, // Nuevo: estado de carga de la lista
            filterTitle: '',    // Nuevo: título del filtro
            // Search queries per section
            searchFilteredList: '',
            searchDelayed: '',
            searchDelayedWo: '',
            searchReady: '',
            searchUpcoming: '',
        });

        this.rootRef = useRef("root");

        // Lifecycle hooks
        onMounted(async () => {
            const rootEl = this.rootRef.el;
            const actionClient = rootEl?.closest(".o_action_client");

            if (actionClient) {
                actionClient.classList.add("o_action_client_scrollable");
            }

            await this.loadDashboardData();
            this.startAutoRefresh();
        });

        onWillUnmount(() => {
            this.stopAutoRefresh();
        });
    }

    /**
     * Carga los datos del dashboard desde el backend
     */
    async loadDashboardData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "mrp.production",
                "get_dashboard_data",
                []
            );

            this.state.data = data;
            this.state.lastUpdate = new Date();
            this.state.loading = false;

            console.log("Dashboard data loaded:", data);
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.notification.add(
                "Error al cargar datos del dashboard",
                {
                    type: "danger",
                    title: "Error",
                }
            );
            this.state.loading = false;
        }
    }

    /**
     * Inicia el auto-refresh del dashboard cada 30 segundos
     */
    startAutoRefresh() {
        if (this.state.autoRefresh) {
            this.refreshTimer = setInterval(() => {
                // Solo refrescamos los contadores si NO hay un filtro activo
                // para evitar que la lista desaparezca o parpadee.
                if (!this.state.activeFilter) {
                    this.loadDashboardData();
                }
            }, this.state.refreshInterval * 1000);
        }
    }

    /**
     * Detiene el auto-refresh
     */
    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    /**
     * Toggle del auto-refresh
     */
    toggleAutoRefresh() {
        this.state.autoRefresh = !this.state.autoRefresh;

        if (this.state.autoRefresh) {
            this.startAutoRefresh();
            this.notification.add(
                "Auto-refresh activado",
                {
                    type: "success",
                }
            );
        } else {
            this.stopAutoRefresh();
            this.notification.add(
                "Auto-refresh desactivado",
                {
                    type: "info",
                }
            );
        }
    }

    /**
     * Refresca manualmente los datos
     */
    async refreshDashboard() {
        await this.loadDashboardData();
        // Si hay filtro activo, también refrescamos la lista
        if (this.state.activeFilter) {
             // Re-simulamos el click para refrescar
             // Ojo: openCases requiere 'stage' string original, que no guardamos.
             // Simplificación: Solo recargamos contadores por ahora.
        }

        this.notification.add(
            "Dashboard actualizado",
            {
                type: "success",
            }
        );
    }

    /**
     * Limpia el filtro y vuelve al dashboard principal
     */
    clearFilter() {
        this.state.activeFilter = null;
        this.state.orderList = [];
        this.state.filterTitle = '';
        this.state.searchFilteredList = '';
    }

    async openCases(stage) {
        let filterType = 'stage';
        let stageArg = stage;

        // 1. Mapeo de tarjetas especiales a tipos de filtro
        const specialFilters = ["active", "delayed", "urgent", "pending", "vip", "frozen", "completed"];

        if (specialFilters.includes(stage)) {
            filterType = stage;
            stageArg = false; // No es una etapa, es un filtro de estado
        } else {
            // 2. Mapeo de nombres de etapa del frontend a valores del backend
            const stageMapping = {
                'test': 'testing', // 'test' en el frontend -> 'testing' en el backend
            };
            stageArg = stageMapping[stage] || stage;
        }

        // 3. NUEVA LÓGICA SPA: Cargar datos JSON en lugar de Action
        this.state.loadingList = true;
        this.state.activeFilter = stage;
        
        // Título bonito
        const titles = {
            laboratory: "Laboratorio",
            production: "Producción",
            stopped: "Detenidas",
            test: "Testing",
            vip: "Clientes VIP",
            active: "Todas las Activas",
            delayed: "Órdenes Retrasadas",
            urgent: "Órdenes Urgentes",
            pending: "Mensajería / Pendientes",
            frozen: "Congeladas",
            completed: "Completadas"
        };
        this.state.filterTitle = titles[stage] || stage;

        try {
            const orders = await this.orm.call(
                "mrp.production",
                "get_dashboard_order_list",
                [filterType, stageArg]
            );
            
            this.state.orderList = orders;
            console.log("Filtered orders loaded:", orders);
            
        } catch (error) {
            console.error("Error loading order list:", error);
            this.notification.add("No se pudo cargar la lista de órdenes.", { type: "danger" });
            this.state.activeFilter = null; // Revertir
        } finally {
            this.state.loadingList = false;
        }
    }

    openActiveOrders() {
        return this.openCases("active");
    }

    /**
     * Abre una orden específica con navegación entre órdenes del mismo filtro.
     * Pasa la lista de IDs para habilitar el pager nativo "X / Y < >" de Odoo.
     * @param {number} orderId - ID de la orden a abrir
     * @param {string} [source] - Fuente de la lista ('filtered', 'delayed', 'delayed_wo', 'ready', 'upcoming')
     */
    async openOrder(orderId, source) {
        const resIds = source ? this._getResIdsForSource(source) : [];

        // Open form directly. When resIds > 1, pass them via context so the
        // patched FormController (form_pager_patch.js) injects them into the
        // model — enabling the native "1 / N < >" pager arrows.
        const actionDef = {
            type: "ir.actions.act_window",
            res_model: "mrp.production",
            res_id: orderId,
            views: [[false, "form"]],
            target: "current",
        };

        if (resIds.length > 1) {
            actionDef.context = { dashboard_res_ids: resIds };
        }

        await this.action.doAction(actionDef);
    }

    /**
     * Returns the list of MO IDs for the given source section.
     */
    _getResIdsForSource(source) {
        switch (source) {
            case 'filtered':
                return this.getFilteredOrderList().map(o => o.id);
            case 'delayed':
                return this.getFilteredDelayedDetails().map(o => o.id);
            case 'delayed_wo':
                return [...new Set(this.getFilteredDelayedWoDetails().map(w => w.production_id))];
            case 'ready':
                return [...new Set(this.getFilteredReadyWos().map(w => w.production_id))];
            case 'upcoming':
                return this.getFilteredUpcomingMos().map(m => m.id);
            default:
                return [];
        }
    }

    /**
     * Returns a human-readable title for the given source section.
     */
    _getSourceTitle(source) {
        const titles = {
            'filtered': this.state.filterTitle || 'Órdenes de Manufactura',
            'delayed': 'Órdenes Retrasadas',
            'delayed_wo': 'Operaciones Retrasadas',
            'ready': 'Operaciones Listas para Iniciar',
            'upcoming': 'Próximas a Vencer',
        };
        return titles[source] || 'Órdenes de Manufactura';
    }

    /**
     * Borra una orden verificando permisos primero.
     * Si falla (porque no es manager), muestra error y NO actualiza la vista.
     */
    async deleteOrder(orderId, event) {
        // Detenemos la propagación si el botón está dentro de una tarjeta clicable
        if (event) {
            event.stopPropagation();
        }

        // 1. Confirmación de seguridad
        const confirmed = confirm("¿Estás seguro de que quieres eliminar esta orden?");
        if (!confirmed) return;

        // Guardamos el estado de carga para bloquear botones si quieres
        this.state.loading = true;

        try {
            // 2. Intentamos borrar en el Backend PRIMERO
            // Llamamos al método 'unlink' del modelo mrp.production
            await this.orm.call("mrp.production", "unlink", [[orderId]]);

            // 3. ÉXITO: Si llegamos aquí, el backend dijo "OK".
            // Ahora sí actualizamos la interfaz.

            // Opción A: Recargar todo el dashboard (más seguro para actualizar contadores)
            await this.loadDashboardData();

            // Notificación verde
            this.notification.add("Orden eliminada correctamente", { type: "success" });

        } catch (error) {
            // 4. ERROR: Si el usuario no es Manager, Odoo lanza excepción aquí.
            console.error("Error al borrar:", error);

            // Extraemos el mensaje de error de Odoo
            let msg = "No se pudo eliminar la orden.";
            if (error.data && error.data.message) {
                msg = error.data.message; // Mensaje técnico
            } else if (error.message) {
                msg = error.message;
            }

            // Mostramos la alerta ROJA
            this.notification.add(msg, {
                type: "danger",
                title: "Acceso Denegado",
                sticky: true
            });

            // IMPORTANTE: NO hacemos nada con this.state.data.
            // La orden se queda visible en la pantalla.
        } finally {
            this.state.loading = false;
        }
    }

    // ============================================
    // SEARCH / FILTER METHODS
    // ============================================

    /**
     * Generic filter: matches query against doctor, patient, product, name fields
     */
    _filterBySearch(items, query) {
        if (!query || !query.trim()) return items;
        const q = query.toLowerCase().trim();
        return items.filter(item => {
            const fields = [
                item.doctor || item.doctor_name || '',
                item.patient || '',
                item.product || item.product_name || '',
                item.name || item.production_name || '',
            ];
            return fields.some(f => f.toLowerCase().includes(q));
        });
    }

    onSearchFilteredList(ev) {
        this.state.searchFilteredList = ev.target.value;
    }

    onSearchDelayed(ev) {
        this.state.searchDelayed = ev.target.value;
    }

    onSearchDelayedWo(ev) {
        this.state.searchDelayedWo = ev.target.value;
    }

    onSearchReady(ev) {
        this.state.searchReady = ev.target.value;
    }

    onSearchUpcoming(ev) {
        this.state.searchUpcoming = ev.target.value;
    }

    getFilteredOrderList() {
        return this._filterBySearch(this.state.orderList, this.state.searchFilteredList);
    }

    getFilteredDelayedDetails() {
        const items = this.state.data?.delayed_details || [];
        return this._filterBySearch(items, this.state.searchDelayed);
    }

    getFilteredDelayedWoDetails() {
        const items = (this.state.data?.delayed_wo_details || []).filter(
            w => w.state !== 'waiting' && w.state !== 'pending' && w.state !== 'draft'
        );
        return this._filterBySearch(items, this.state.searchDelayedWo);
    }

    getFilteredReadyWos() {
        const items = this.state.data?.ready_wo_details || [];
        return this._filterBySearch(items, this.state.searchReady);
    }

    getFilteredUpcomingMos() {
        const items = this.state.data?.upcoming_mo_details || [];
        return this._filterBySearch(items, this.state.searchUpcoming);
    }

    /**
     * Obtiene el nombre legible de una etapa
     */
    getStageName(stage) {
        const stageNames = {
            laboratory: "Laboratorio",
            production: "Producción",
            stopped: "Detenidas",
            test: "Testing",
        };
        return stageNames[stage] || stage;
    }

    /**
     * Formatea la fecha de última actualización
     */
    getLastUpdateFormatted() {
        if (!this.state.lastUpdate) {
            return "Nunca";
        }

        const now = new Date();
        const diff = Math.floor((now - this.state.lastUpdate) / 1000); // segundos

        if (diff < 60) {
            return `Hace ${diff}s`;
        } else if (diff < 3600) {
            return `Hace ${Math.floor(diff / 60)}m`;
        } else {
            return `Hace ${Math.floor(diff / 3600)}h`;
        }
    }

    /**
     * Calcula el porcentaje de progreso para órdenes retrasadas
     */
    getDelayPercentage(order) {
        if (!order.deadline || order.deadline === 0) {
            return 100;
        }
        return Math.min(100, Math.round((order.time / order.deadline) * 100));
    }

    /**
     * Obtiene la clase CSS para el badge de etapa
     */
    getStageBadgeClass(stage) {
        const classes = {
            laboratory: "badge-laboratory",
            production: "badge-production",
            stopped: "badge-stopped",
            test: "badge-testing",
        };
        return classes[stage] || "badge-default";
    }
}

// Template del componente
ManufacturingDashboard.template = "custom_manufacturing_dashboard.Dashboard";

// OWL 2 requires static props for all components
ManufacturingDashboard.props = {
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    updateGlobalState: { type: Function, optional: true },
    updateActionState: { type: Function, optional: true },
    globalState: { type: Object, optional: true },
    className: { type: String, optional: true },
};

// Registrar el componente como acción
registry.category("actions").add("manufacturing_dashboard", ManufacturingDashboard);
