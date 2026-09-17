package com.project117.mobile

import com.project117.mobile.data.backend.DemoBackend
import com.project117.mobile.domain.model.*
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class DemoBackendTest {

    private lateinit var demoBackend: DemoBackend

    @Before
    fun setup() {
        demoBackend = DemoBackend()
    }

    @Test
    fun testCanonicalEquipmentP102ExistsAndHasAbnormalVibration() = runTest {
        val result = demoBackend.getEquipment("EQ-P102")
        assertTrue(result is BackendResult.Success)

        val eq = (result as BackendResult.Success).data
        assertEquals("Pump P-102", eq.name)
        assertEquals(EquipmentStatus.DEGRADED, eq.status)
        assertEquals("EQ-P102-VIB", eq.qrCode)

        val vibReading = eq.readings.find { it.parameter.contains("Vibration", ignoreCase = true) }
        assertNotNull(vibReading)
        assertEquals("7.8", vibReading!!.value)
        assertFalse(vibReading.isNominal)
    }

    @Test
    fun testIdentifyEquipmentByQrCode() = runTest {
        val res = demoBackend.identifyEquipment("EQ-P102-VIB")
        assertTrue(res is BackendResult.Success)
        assertEquals("EQ-P102", (res as BackendResult.Success).data.id)

        val notFound = demoBackend.identifyEquipment("UNKNOWN-QR")
        assertTrue(notFound is BackendResult.NotFound)
    }

    @Test
    fun testCanonicalWorkOrderExistsWithSteps() = runTest {
        val res = demoBackend.getWorkOrder("WO-2026-0891")
        assertTrue(res is BackendResult.Success)

        val wo = (res as BackendResult.Success).data
        assertEquals(WorkOrderPriority.CRITICAL, wo.priority)
        assertEquals("EQ-P102", wo.equipmentId)
        assertTrue(wo.steps.isNotEmpty())
        assertTrue(wo.steps.any { it.evidenceRequired })
    }

    @Test
    fun testCanonicalSop042Exists() = runTest {
        val res = demoBackend.getSop("SOP-MEC-042")
        assertTrue(res is BackendResult.Success)

        val sop = (res as BackendResult.Success).data
        assertTrue(sop.title.contains("Vibration Protocol", ignoreCase = true))
        assertTrue(sop.content.contains("ISO 10816"))
    }

    @Test
    fun testSupervisorApprovalDecisionFlow() = runTest {
        val res = demoBackend.decideApproval("APP-042", ApprovalDecision.APPROVE, "Verified on site")
        assertTrue(res is BackendResult.Success)

        val app = (res as BackendResult.Success).data
        assertEquals(ApprovalStatus.APPROVED, app.status)

        // Verifying work order also transitions upon approval
        val woRes = demoBackend.getWorkOrder("WO-2026-0891")
        assertTrue(woRes is BackendResult.Success)
        assertEquals(WorkOrderStatus.COMPLETED, (woRes as BackendResult.Success).data.status)
    }

    @Test
    fun testAssistantDeterministicResponses() = runTest {
        val resPump = demoBackend.sendMessage("What is the status of Pump P-102?", null)
        assertTrue(resPump is BackendResult.Success)
        assertTrue((resPump as BackendResult.Success).data.contains("7.8 mm/s"))

        val resSop = demoBackend.sendMessage("What SOP applies to this pump?", null)
        assertTrue(resSop is BackendResult.Success)
        assertTrue((resSop as BackendResult.Success).data.contains("SOP-MEC-042"))
    }

    @Test
    fun testRolePermissionsEnforcement() = runTest {
        val techLogin = demoBackend.login("technician", "pass", "token")
        assertTrue(techLogin is BackendResult.Success)
        val techSession = (techLogin as BackendResult.Success).data
        assertEquals(UserRole.TECHNICIAN, techSession.role)
        assertFalse(techSession.role.isSupervisorOrAbove)
        assertFalse(techSession.hasPermission(Permissions.DECIDE_APPROVALS))

        val supLogin = demoBackend.login("supervisor", "pass", "token")
        assertTrue(supLogin is BackendResult.Success)
        val supSession = (supLogin as BackendResult.Success).data
        assertEquals(UserRole.SUPERVISOR, supSession.role)
        assertTrue(supSession.role.isSupervisorOrAbove)
        assertTrue(supSession.hasPermission(Permissions.DECIDE_APPROVALS))
    }
}
