package com.project117.mobile.data.backend

import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.*
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class DemoBackend @Inject constructor() : FieldBackend {

    // ─── Equipment State ──────────────────────────────────────────────────────
    private val equipmentList = mutableListOf(
        Equipment(
            id = "EQ-P102",
            name = "Pump P-102",
            type = "Centrifugal Slurry Pump",
            location = "Processing Plant - Unit 4B",
            status = EquipmentStatus.DEGRADED,
            qrCode = "EQ-P102-VIB",
            barcode = "P102-883921",
            manufacturer = "FlowServe Heavy Industries",
            model = "Mark 3 Slurry 4x3-10",
            serialNumber = "FS-2021-9941A",
            lastMaintenanceDate = "2026-06-15",
            nextMaintenanceDate = "2026-09-15",
            metadata = mapOf(
                "Rated RPM" to "1780",
                "Impeller Dia" to "280 mm",
                "Slurry Density" to "1.35 kg/L",
                "Criticality" to "Tier 1 (High Impact)"
            ),
            readings = listOf(
                EquipmentReading("Vibration Spectrum (RMS)", "7.8", "mm/s", "Just now", isNominal = false),
                EquipmentReading("Bearing Temperature", "82.4", "°C", "Just now", isNominal = false),
                EquipmentReading("Discharge Pressure", "4.2", "bar", "1 min ago", isNominal = true),
                EquipmentReading("Motor Current", "48.6", "A", "1 min ago", isNominal = true),
                EquipmentReading("Suction Head", "1.8", "bar", "2 min ago", isNominal = true)
            )
        ),
        Equipment(
            id = "EQ-M201",
            name = "Drive Motor M-201",
            type = "3-Phase Induction Motor",
            location = "Processing Plant - Unit 4B",
            status = EquipmentStatus.OPERATIONAL,
            qrCode = "EQ-M201-DRV",
            barcode = "M201-441209",
            manufacturer = "Siemens Industrial",
            model = "1LA8 355-4EB90",
            serialNumber = "SIE-2022-7718",
            lastMaintenanceDate = "2026-07-20",
            nextMaintenanceDate = "2026-10-20",
            metadata = mapOf(
                "Power" to "75 kW",
                "Voltage" to "415 V",
                "Insulation Class" to "Class H"
            ),
            readings = listOf(
                EquipmentReading("Vibration", "1.6", "mm/s", "Just now", isNominal = true),
                EquipmentReading("Winding Temp", "64.2", "°C", "Just now", isNominal = true),
                EquipmentReading("Line Current", "48.2", "A", "Just now", isNominal = true)
            )
        ),
        Equipment(
            id = "EQ-V104",
            name = "Relief Valve V-104",
            type = "Pneumatic Control Valve",
            location = "Processing Plant - Line 3 Bypass",
            status = EquipmentStatus.OPERATIONAL,
            qrCode = "EQ-V104-REL",
            barcode = "V104-110482",
            manufacturer = "Fisher Controls",
            model = "ED-5000 High Pressure",
            serialNumber = "FSH-2023-1120",
            lastMaintenanceDate = "2026-05-10",
            nextMaintenanceDate = "2026-11-10",
            metadata = mapOf(
                "Set Pressure" to "6.0 bar",
                "Body Material" to "316 Stainless Steel"
            ),
            readings = listOf(
                EquipmentReading("Position", "0.0", "% (Closed)", "Just now", isNominal = true),
                EquipmentReading("Upstream Pressure", "4.2", "bar", "Just now", isNominal = true)
            )
        )
    )

    // ─── Work Orders State ────────────────────────────────────────────────────
    private val workOrders = mutableListOf(
        WorkOrder(
            id = "WO-2026-0891",
            title = "Urgent Vibration Inspection & Bearing Check",
            description = "AI condition monitor detected abnormal vibration (7.8 mm/s) on Pump P-102 outboard bearing. Complete on-site inspection, capture physical evidence, and determine if shutdown is required.",
            status = WorkOrderStatus.IN_PROGRESS,
            priority = WorkOrderPriority.CRITICAL,
            assignedTo = "Technician",
            equipmentId = "EQ-P102",
            equipmentName = "Pump P-102 (Centrifugal Slurry Pump)",
            dueDate = "Today 16:00",
            createdAt = "2026-09-14 08:30",
            updatedAt = "2026-09-14 09:15",
            steps = listOf(
                WorkOrderStep(1, "Outboard Bearing Visual Inspection", "Inspect housing for oil weeping, casing discoloration, and loose mount bolts.", isCompleted = true, evidenceRequired = true, evidenceIds = listOf("EVID-001")),
                WorkOrderStep(2, "Manual Vibration Spectrum Reading", "Attach handheld accelerometer to vertical and horizontal measuring ports and record peak velocity.", isCompleted = false, evidenceRequired = true),
                WorkOrderStep(3, "Mechanical Seal Inspection", "Check mechanical seal quench chamber for signs of slurry leakage.", isCompleted = false, evidenceRequired = true),
                WorkOrderStep(4, "Lubrication Level Verification", "Confirm oil level in sight glass and check lubricant clarity.", isCompleted = false, evidenceRequired = false)
            ),
            notes = "Spike observed following shift handover. Operator reported audible humming noise."
        ),
        WorkOrder(
            id = "WO-2026-0885",
            title = "Routine Motor M-201 Greasing",
            description = "Bi-monthly motor drive-end bearing grease replenishment according to manufacturer schedule.",
            status = WorkOrderStatus.OPEN,
            priority = WorkOrderPriority.MEDIUM,
            assignedTo = "Technician",
            equipmentId = "EQ-M201",
            equipmentName = "Drive Motor M-201",
            dueDate = "Tomorrow 17:00",
            createdAt = "2026-09-13 14:00",
            updatedAt = "2026-09-13 14:00",
            steps = listOf(
                WorkOrderStep(1, "Purge old grease", "Open drain plug and purge 30g NLGI 2 synthetic grease.", false, false),
                WorkOrderStep(2, "Inspect run-out", "Check shaft runout using dial indicator.", false, false)
            )
        )
    )

    // ─── SOPs ─────────────────────────────────────────────────────────────────
    private val sops = listOf(
        Sop(
            id = "SOP-MEC-042",
            title = "Centrifugal Pump Bearing Inspection & Vibration Protocol",
            category = "Mechanical Maintenance",
            version = "v3.2",
            summary = "Standard procedure for diagnosing vibration exceeding 4.5 mm/s on heavy slurry pump bearing assemblies and preventing catastrophic shaft seizure.",
            content = """
                1. PURPOSE & SAFETY
                This procedure applies whenever vibration velocity exceeds 4.5 mm/s (ISO 10816 Zone C/D). Wear safety goggles, ear protection, and heat-resistant gloves.

                2. INITIAL ASSESSMENT
                - Verify machine tag (EQ-P102) matches work order before touching machine.
                - Observe pump operational sound. Distinct rhythmic knocking indicates bearing outer race fatigue.
                - Check bearing housing temperature with IR thermometer. If > 85°C, prepare for immediate shutdown.

                3. VIBRATION MEASUREMENT
                - Clean sensor contact point on vertical and horizontal bearing housing faces.
                - Capture 3-axis spectrum reading: Overall RMS velocity (10Hz - 1000Hz).
                - Document reading in mobile app and take photo of sensor display.

                4. MECHANICAL SEAL CHECK
                - Inspect seal leakage collector. If slurry droplet rate > 10 drops/min, mechanical seal has breached secondary O-ring.

                5. ESCALATION & APPROVAL
                - If vibration > 7.0 mm/s and temperature > 80°C, technician must request Supervisor Approval (APP-042) for emergency shutdown and bearing replacement.
            """.trimIndent(),
            equipmentTypes = listOf("Centrifugal Slurry Pump", "Submersible Pump"),
            tags = listOf("Vibration", "Bearings", "Slurry Pump", "ISO 10816", "High Priority"),
            lastUpdated = "2026-08-01"
        ),
        Sop(
            id = "SOP-ELEC-018",
            title = "3-Phase Induction Motor Periodic Maintenance",
            category = "Electrical Maintenance",
            version = "v2.1",
            summary = "Lubrication, insulation resistance testing, and vibration baseline checks for 415V motors.",
            content = "Detailed instructions for electrical lock-out/tag-out and insulation resistance testing...",
            equipmentTypes = listOf("3-Phase Induction Motor"),
            tags = listOf("Motor", "Electrical", "Greasing"),
            lastUpdated = "2026-05-15"
        )
    )

    // ─── Agent Tasks ──────────────────────────────────────────────────────────
    private val agentTasks = mutableListOf(
        AgentTask(
            id = "AT-0891",
            title = "Bearing Vibration Anomaly Verification",
            description = "AI predictive model detected 310% vibration spike on outboard bearing. Complete on-site inspection, capture photo evidence of measuring port, and submit measurement.",
            source = "AI Predictive Maintenance Agent",
            priority = AgentTaskPriority.URGENT,
            status = AgentTaskStatus.PENDING,
            equipmentId = "EQ-P102",
            equipmentName = "Pump P-102",
            workOrderId = "WO-2026-0891",
            instructions = "1. Confirm bearing temperature.\n2. Record vertical & horizontal vibration.\n3. Photograph housing condition.",
            evidenceRequired = true,
            dueBy = "Today 15:00",
            createdAt = "2026-09-14 09:00"
        )
    )

    // ─── Approvals ────────────────────────────────────────────────────────────
    private val approvals = mutableListOf(
        Approval(
            id = "APP-042",
            title = "Emergency Shutdown & Seal Assembly Replacement",
            description = "Technician verified severe outboard bearing vibration (7.8 mm/s) and secondary seal degradation. Authorize 4-hour maintenance shutdown on Unit 4B Slurry Line.",
            workOrderId = "WO-2026-0891",
            workOrderTitle = "Urgent Vibration Inspection & Bearing Check",
            equipmentId = "EQ-P102",
            equipmentName = "Pump P-102 (Centrifugal Slurry Pump)",
            consequence = "Halts Slurry Circuit 4B for 4 hours. Estimated downstream production buffer capacity: 5.5 hours.",
            requestedBy = "Tech. Field Operator",
            requestedAt = "2026-09-14 09:25",
            deadline = "Today 16:30",
            evidenceIds = listOf("EVID-001"),
            status = ApprovalStatus.PENDING
        )
    )

    // ─── Notifications ────────────────────────────────────────────────────────
    private val notifications = mutableListOf(
        AppNotification(
            id = "NOTIF-001",
            type = NotificationType.ALERT,
            title = "CRITICAL ALERT: High Vibration on Pump P-102",
            body = "Vibration reached 7.8 mm/s (threshold: 4.5 mm/s). Immediate inspection advised.",
            timestamp = "10 min ago",
            isRead = false,
            referenceId = "EQ-P102",
            referenceType = "equipment"
        ),
        AppNotification(
            id = "NOTIF-002",
            type = NotificationType.AGENT_TASK,
            title = "New Agent Task Assigned",
            body = "Task AT-0891 generated by Predictive Agent for Pump P-102.",
            timestamp = "25 min ago",
            isRead = false,
            referenceId = "AT-0891",
            referenceType = "agent_task"
        ),
        AppNotification(
            id = "NOTIF-003",
            type = NotificationType.APPROVAL_REQUIRED,
            title = "Approval Required: Emergency Shutdown",
            body = "Approval APP-042 pending for Pump P-102 shutdown on Slurry Line 4B.",
            timestamp = "5 min ago",
            isRead = false,
            referenceId = "APP-042",
            referenceType = "approval"
        )
    )

    // ─── Reported Issues ──────────────────────────────────────────────────────
    private val issues = mutableListOf<Issue>()

    // ─── Implementation of FieldBackend ───────────────────────────────────────

    override suspend fun checkHealth(): BackendResult<Boolean> {
        return BackendResult.Success(true)
    }

    override suspend fun enroll(deviceId: String, enrollmentCode: String): BackendResult<String> {
        return if (enrollmentCode.isNotBlank()) {
            BackendResult.Success("DEMO-DEVICE-TOKEN-${UUID.randomUUID().toString().take(8)}")
        } else {
            BackendResult.Error("Invalid enrollment code", 400)
        }
    }

    override suspend fun login(username: String, password: String, deviceToken: String): BackendResult<UserSession> {
        val role = when (username.lowercase().trim()) {
            "supervisor", "admin", "lead" -> UserRole.SUPERVISOR
            "operator" -> UserRole.OPERATOR
            "inspector", "qa", "quality" -> UserRole.OPERATOR
            else -> UserRole.TECHNICIAN
        }

        val permissions = when (role) {
            UserRole.SUPERVISOR, UserRole.ADMIN -> setOf(
                Permissions.VIEW_EQUIPMENT, Permissions.VIEW_WORK_ORDERS, Permissions.UPDATE_WORK_ORDERS,
                Permissions.VIEW_SOP, Permissions.REPORT_ISSUES, Permissions.CAPTURE_EVIDENCE,
                Permissions.USE_ASSISTANT, Permissions.VIEW_APPROVALS, Permissions.DECIDE_APPROVALS,
                Permissions.VIEW_AGENT_TASKS, Permissions.COMPLETE_AGENT_TASKS
            )
            UserRole.OPERATOR -> setOf(
                Permissions.VIEW_EQUIPMENT, Permissions.VIEW_WORK_ORDERS, Permissions.VIEW_SOP,
                Permissions.REPORT_ISSUES, Permissions.CAPTURE_EVIDENCE, Permissions.USE_ASSISTANT
            )
            else -> setOf(
                Permissions.VIEW_EQUIPMENT, Permissions.VIEW_WORK_ORDERS, Permissions.UPDATE_WORK_ORDERS,
                Permissions.VIEW_SOP, Permissions.REPORT_ISSUES, Permissions.CAPTURE_EVIDENCE,
                Permissions.USE_ASSISTANT, Permissions.VIEW_AGENT_TASKS, Permissions.COMPLETE_AGENT_TASKS
            )
        }

        val displayName = when (role) {
            UserRole.SUPERVISOR -> "Sarah Jenkins (Supervisor)"
            UserRole.OPERATOR -> "Alex Rivera (Operator)"
            else -> "Rajesh Sharma (Field Technician)"
        }

        return BackendResult.Success(
            UserSession(
                userId = "USR-${username.lowercase()}",
                username = username,
                displayName = displayName,
                role = role,
                permissions = permissions,
                accessToken = "DEMO-JWT-ACCESS-TOKEN",
                refreshToken = "DEMO-JWT-REFRESH-TOKEN"
            )
        )
    }

    override suspend fun refreshToken(refreshToken: String): BackendResult<String> {
        return BackendResult.Success("DEMO-JWT-REFRESHED-TOKEN")
    }

    override suspend fun logout(accessToken: String): BackendResult<Unit> {
        return BackendResult.Success(Unit)
    }

    override suspend fun getMe(accessToken: String): BackendResult<UserSession> {
        return login("technician", "demo", "demo-token")
    }

    override suspend fun getEquipmentList(): BackendResult<List<Equipment>> {
        return BackendResult.Success(equipmentList.toList())
    }

    override suspend fun getEquipment(id: String): BackendResult<Equipment> {
        val eq = equipmentList.find { it.id.equals(id, ignoreCase = true) }
            ?: return BackendResult.NotFound
        return BackendResult.Success(eq)
    }

    override suspend fun identifyEquipment(qrCode: String): BackendResult<Equipment> {
        val trimmed = qrCode.trim()
        val eq = equipmentList.find {
            it.qrCode.equals(trimmed, ignoreCase = true) ||
            it.id.equals(trimmed, ignoreCase = true) ||
            it.barcode.equals(trimmed, ignoreCase = true)
        } ?: return BackendResult.NotFound
        return BackendResult.Success(eq)
    }

    override suspend fun getWorkOrders(): BackendResult<List<WorkOrder>> {
        return BackendResult.Success(workOrders.toList())
    }

    override suspend fun getWorkOrder(id: String): BackendResult<WorkOrder> {
        val wo = workOrders.find { it.id.equals(id, ignoreCase = true) }
            ?: return BackendResult.NotFound
        return BackendResult.Success(wo)
    }

    override suspend fun updateWorkOrder(id: String, status: WorkOrderStatus, notes: String?): BackendResult<WorkOrder> {
        val idx = workOrders.indexOfFirst { it.id.equals(id, ignoreCase = true) }
        if (idx == -1) return BackendResult.NotFound

        val current = workOrders[idx]
        val updated = current.copy(
            status = status,
            notes = notes ?: current.notes,
            updatedAt = "Just now"
        )
        workOrders[idx] = updated
        return BackendResult.Success(updated)
    }

    override suspend fun getAgentTasks(): BackendResult<List<AgentTask>> {
        return BackendResult.Success(agentTasks.toList())
    }

    override suspend fun acknowledgeAgentTask(id: String): BackendResult<AgentTask> {
        val idx = agentTasks.indexOfFirst { it.id.equals(id, ignoreCase = true) }
        if (idx == -1) return BackendResult.NotFound

        val updated = agentTasks[idx].copy(status = AgentTaskStatus.IN_PROGRESS)
        agentTasks[idx] = updated
        return BackendResult.Success(updated)
    }

    override suspend fun completeAgentTask(id: String, notes: String?, evidenceIds: List<String>): BackendResult<AgentTask> {
        val idx = agentTasks.indexOfFirst { it.id.equals(id, ignoreCase = true) }
        if (idx == -1) return BackendResult.NotFound

        val updated = agentTasks[idx].copy(
            status = AgentTaskStatus.COMPLETED,
            instructions = "${agentTasks[idx].instructions}\n[Completed with evidence: ${evidenceIds.joinToString()}]"
        )
        agentTasks[idx] = updated
        return BackendResult.Success(updated)
    }

    override suspend fun getApprovals(): BackendResult<List<Approval>> {
        return BackendResult.Success(approvals.toList())
    }

    override suspend fun decideApproval(id: String, decision: ApprovalDecision, notes: String?): BackendResult<Approval> {
        val idx = approvals.indexOfFirst { it.id.equals(id, ignoreCase = true) }
        if (idx == -1) return BackendResult.NotFound

        val newStatus = if (decision == ApprovalDecision.APPROVE) ApprovalStatus.APPROVED else ApprovalStatus.REJECTED
        val updated = approvals[idx].copy(status = newStatus)
        approvals[idx] = updated

        // If approved, update work order state to COMPLETED or PENDING_APPROVAL
        if (decision == ApprovalDecision.APPROVE) {
            val woIdx = workOrders.indexOfFirst { it.id == updated.workOrderId }
            if (woIdx != -1) {
                workOrders[woIdx] = workOrders[woIdx].copy(
                    status = WorkOrderStatus.COMPLETED,
                    notes = "Emergency shutdown approved by supervisor. Work order completed."
                )
            }
        }
        return BackendResult.Success(updated)
    }

    override suspend fun sendMessage(message: String, context: AssistantContext?): BackendResult<String> {
        val query = message.lowercase().trim()
        val response = when {
            query.contains("sop") || query.contains("procedure") -> {
                "SOP-MEC-042 ('Centrifugal Pump Bearing Inspection & Vibration Protocol') applies to Pump P-102. Step 1 requires visual inspection; Step 2 requires manual accelerometer verification."
            }
            query.contains("why") || query.contains("assigned") || query.contains("reason") -> {
                "Predictive AI Agent detected a 310% vibration spike on outboard bearing sensor exceeding the 4.5 mm/s ISO 10816 limit. Field inspection is required to prevent catastrophic shaft seizure."
            }
            query.contains("next") || query.contains("check") || query.contains("action") -> {
                "Follow Step 2 of WO-2026-0891: Record manual vibration spectrum reading with portable sensor and upload photo evidence. If vibration remains > 7.0 mm/s, request Supervisor Approval for shutdown."
            }
            query.contains("shutdown") || query.contains("approval") -> {
                "Shutdown approval request APP-042 has been filed for Pump P-102. Requires Supervisor role to approve."
            }
            query.contains("pump") || query.contains("p-102") || query.contains("p102") || query.contains("status") || query.contains("vibration") || query.contains("telemetry") -> {
                "Pump P-102 (Centrifugal Slurry Pump) is in DEGRADED condition. Telemetry reports abnormal vibration at 7.8 mm/s (nominal 2.5 mm/s) and bearing temp at 82.4°C. Active work order WO-2026-0891 and Agent Task AT-0891 are assigned."
            }
            else -> {
                "Project 117 Field Assistant: Currently monitoring 3 operational units. Pump P-102 has an active vibration alert (7.8 mm/s). You can ask about equipment telemetry, assigned SOPs, or work order steps."
            }
        }
        return BackendResult.Success(response)
    }

    override suspend fun getSopList(): BackendResult<List<Sop>> {
        return BackendResult.Success(sops)
    }

    override suspend fun getSop(id: String): BackendResult<Sop> {
        val sop = sops.find { it.id.equals(id, ignoreCase = true) } ?: return BackendResult.NotFound
        return BackendResult.Success(sop)
    }

    override suspend fun reportIssue(
        equipmentId: String,
        description: String,
        severity: IssueSeverity,
        evidenceIds: List<String>
    ): BackendResult<Issue> {
        val newIssue = Issue(
            id = "ISSUE-${UUID.randomUUID().toString().take(6).uppercase()}",
            equipmentId = equipmentId,
            equipmentName = equipmentList.find { it.id == equipmentId }?.name ?: equipmentId,
            description = description,
            severity = severity,
            reportedBy = "Technician",
            reportedAt = "Just now",
            evidenceIds = evidenceIds,
            workOrderId = "WO-2026-0891",
            syncStatus = SyncStatus.SYNCED
        )
        issues.add(newIssue)
        return BackendResult.Success(newIssue)
    }

    override suspend fun uploadEvidence(
        localPath: String,
        type: EvidenceType,
        equipmentId: String?,
        workOrderId: String?,
        caption: String?
    ): BackendResult<String> {
        val docId = "DOC-EVID-${UUID.randomUUID().toString().take(8).uppercase()}"
        return BackendResult.Success(docId)
    }

    override suspend fun getNotifications(): BackendResult<List<AppNotification>> {
        return BackendResult.Success(notifications.toList())
    }

    override suspend fun markNotificationRead(id: String): BackendResult<Unit> {
        val idx = notifications.indexOfFirst { it.id == id }
        if (idx != -1) {
            notifications[idx] = notifications[idx].copy(isRead = true)
        }
        return BackendResult.Success(Unit)
    }
}
