/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

/**
 * Employee Workload Dashboard - Dashboard Individual para Empleados
 * Muestra cola de operaciones asignadas con timer en tiempo real y alertas en cascada
 */
export class EmployeeWorkloadDashboard extends Component {
    setup() {
        // Servicios de Odoo
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        // Estado reactivo del componente
        this.state = useState({
            loading: true,
            data: null,
            lastUpdate: null,
            autoRefresh: true,
            refreshInterval: 30, // segundos
            currentTime: new Date(), // Para timer en tiempo real
        });

        // Lifecycle hooks
        onMounted(async () => {
            await this.loadEmployeeData();
            this.startAutoRefresh();
            this.startRealtimeTimer();
        });

        onWillUnmount(() => {
            this.stopAutoRefresh();
            this.stopRealtimeTimer();
        });
    }

    /**
     * Carga los datos del empleado desde el backend
     */
    async loadEmployeeData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "mrp.workorder",
                "get_employee_workload_dashboard",
                []
            );

            this.state.data = data;
            this.state.lastUpdate = new Date();
            this.state.loading = false;

            console.log("Employee dashboard data loaded:", data);
        } catch (error) {
            console.error("Error loading employee dashboard data:", error);
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
                this.loadEmployeeData();
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
     * Inicia el timer en tiempo real (actualiza cada segundo)
     */
    startRealtimeTimer() {
        this.realtimeTimer = setInterval(() => {
            this.state.currentTime = new Date();
        }, 1000);
    }

    /**
     * Detiene el timer en tiempo real
     */
    stopRealtimeTimer() {
        if (this.realtimeTimer) {
            clearInterval(this.realtimeTimer);
            this.realtimeTimer = null;
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
        await this.loadEmployeeData();
        this.notification.add(
            "Dashboard actualizado",
            {
                type: "success",
            }
        );
    }

    /**
     * Inicia una operación
     */
    async startOperation(operationId) {
        try {
            await this.orm.call(
                "mrp.workorder",
                "button_start",
                [[operationId]]
            );

            this.notification.add(
                "Operación iniciada",
                {
                    type: "success",
                    title: "Éxito",
                }
            );

            // Recargar datos
            await this.loadEmployeeData();
        } catch (error) {
            console.error("Error starting operation:", error);
            this.notification.add(
                "Error al iniciar operación",
                {
                    type: "danger",
                    title: "Error",
                }
            );
        }
    }

    /**
     * Finaliza una operación
     */
    async finishOperation(operationId) {
        try {
            await this.orm.call(
                "mrp.workorder",
                "button_finish",
                [[operationId]]
            );

            this.notification.add(
                "Operación finalizada",
                {
                    type: "success",
                    title: "Éxito",
                }
            );

            // Recargar datos
            await this.loadEmployeeData();
        } catch (error) {
            console.error("Error finishing operation:", error);
            this.notification.add(
                "Error al finalizar operación",
                {
                    type: "danger",
                    title: "Error",
                }
            );
        }
    }

    /**
     * Abre una operación en form view
     */
    async openOperation(operationId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mrp.workorder",
            res_id: operationId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    /**
     * Abre la orden de producción asociada
     */
    async openProducción(productionId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mrp.production",
            res_id: productionId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    /**
     * Obtiene la clase CSS para el workload status
     */
    getWorkloadStatusClass(status) {
        const classes = {
            available: "status-available",
            busy: "status-busy",
            overloaded: "status-overloaded",
        };
        return classes[status] || "status-available";
    }

    /**
     * Obtiene el icono para el workload status
     */
    getWorkloadStatusIcon(status) {
        const icons = {
            available: "fa-check-circle",
            busy: "fa-hourglass-half",
            overloaded: "fa-exclamation-triangle",
        };
        return icons[status] || "fa-check-circle";
    }

    /**
     * Obtiene el label para el workload status
     */
    getWorkloadStatusLabel(status) {
        const labels = {
            available: "Disponible",
            busy: "Ocupado",
            overloaded: "Sobrecargado",
        };
        return labels[status] || status;
    }

    /**
     * Obtiene el label del departamento
     */
    getDepartmentLabel(department) {
        const labels = {
            diseno: "Diseño",
            fresado: "Fresado",
            ceramica: "Cerámica",
            prensado: "Prensado",
            produccion: "Producción",
            maquillaje: "Maquillaje",
            sistema: "Sistema",
            printer: "Printer",
            mensajeria: "Mensajería",
        };
        return labels[department] || department || "No asignado";
    }

    /**
     * Calcula el porcentaje de progreso de una operación
     */
    getOperationProgress(operation) {
        if (!operation.alert_time_hours || operation.alert_time_hours === 0) {
            return 0;
        }
        const progress = (operation.operation_time / operation.alert_time_hours) * 100;
        return Math.min(100, Math.max(0, progress));
    }

    /**
     * Obtiene la clase CSS para el progress bar según el estado
     */
    getProgressBarClass(operation) {
        if (operation.is_operation_delayed) {
            return "progress-bar-danger";
        } else if (operation.is_operation_urgent) {
            return "progress-bar-warning";
        } else {
            return "progress-bar-success";
        }
    }

    /**
     * Obtiene la clase CSS para el badge de estado de operación
     */
    getOperationStateClass(operation) {
        if (operation.is_operation_delayed) {
            return "badge-danger";
        } else if (operation.is_operation_urgent) {
            return "badge-warning";
        } else if (operation.state === "progress") {
            return "badge-primary";
        } else {
            return "badge-secondary";
        }
    }

    /**
     * Obtiene el label del estado de operación
     */
    getOperationStateLabel(operation) {
        if (operation.is_operation_delayed) {
            return "🔴 Retrasada";
        } else if (operation.is_operation_urgent) {
            return "⚠️ Urgente";
        } else if (operation.state === "progress") {
            return "▶️ En Progreso";
        } else if (operation.state === "ready") {
            return "✓ Lista";
        } else {
            return "⏸ Pendiente";
        }
    }

    /**
     * Verifica si una operación puede ser iniciada
     */
    canStartOperation(operation) {
        return operation.state === "ready" || operation.state === "pending";
    }

    /**
     * Verifica si una operación puede ser finalizada
     */
    canFinishOperation(operation) {
        return operation.state === "progress";
    }

    /**
     * Obtiene la operación actualmente en progreso (si hay)
     */
    getCurrentOperationElapsed() {
        const current = this.getCurrentOperation();
        if (!current) {
            return 0;
        }
        
        // Tiempo base acumulado en BD (en segundos)
        let totalSeconds = current.operation_time * 3600;

        // Si está en progreso, sumamos el tiempo transcurrido desde la última carga de datos
        // hasta el segundo actual del reloj en tiempo real.
        if (current.state === 'progress' && this.state.lastUpdate) {
            const diffSeconds = (this.state.currentTime - this.state.lastUpdate) / 1000;
            // Solo sumamos si la diferencia es positiva
            if (diffSeconds > 0) {
                totalSeconds += diffSeconds;
            }
        }
        
        return totalSeconds;
    }

    /**
     * Formatea tiempo en segundos a HH:MM:SS
     */
    formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
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
}

// Template del componente
EmployeeWorkloadDashboard.template = "custom_manufacturing_dashboard.EmployeeDashboard";

// OWL 2 requires static props for all components
EmployeeWorkloadDashboard.props = {
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    updateGlobalState: { type: Function, optional: true },
    updateActionState: { type: Function, optional: true },
    globalState: { type: Object, optional: true },
    className: { type: String, optional: true },
};

// Registrar el componente como acción
registry.category("actions").add("employee_workload_dashboard", EmployeeWorkloadDashboard);
