package com.project117.mobile.data.remote.api

import com.project117.mobile.data.remote.dto.*
import okhttp3.MultipartBody
import retrofit2.Response
import retrofit2.http.*

/**
 * Retrofit API interface for the Project 117 backend.
 *
 * Base URL is configured at runtime from AppConfig (server configuration screen).
 * Auth header is injected by AuthInterceptor.
 *
 * NO public AI endpoints here. All assistant/chat routes go through the
 * backend which routes to the on-prem AI orchestrator.
 */
interface Project117Api {

    // ─── Health ───────────────────────────────────────────────────────────────

    @GET("health")
    suspend fun getHealth(): Response<HealthResponse>

    // ─── Enrollment ───────────────────────────────────────────────────────────

    @POST("auth/enroll")
    suspend fun enroll(@Body request: EnrollRequest): Response<EnrollResponse>

    // ─── Auth ─────────────────────────────────────────────────────────────────

    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>

    @POST("auth/refresh")
    suspend fun refreshToken(@Body request: RefreshRequest): Response<RefreshResponse>

    @POST("auth/logout")
    suspend fun logout(): Response<Unit>

    @GET("auth/me")
    suspend fun getMe(): Response<MeResponse>

    // ─── Equipment ────────────────────────────────────────────────────────────

    @GET("equipment")
    suspend fun getEquipmentList(): Response<EquipmentListResponse>

    @GET("equipment/{id}")
    suspend fun getEquipment(@Path("id") id: String): Response<EquipmentDto>

    @POST("equipment/identify")
    suspend fun identifyEquipment(@Body request: IdentifyEquipmentRequest): Response<EquipmentDto>

    // ─── Work Orders ──────────────────────────────────────────────────────────

    @GET("work-orders")
    suspend fun getWorkOrders(): Response<WorkOrderListResponse>

    @GET("work-orders/{id}")
    suspend fun getWorkOrder(@Path("id") id: String): Response<WorkOrderDto>

    @POST("work-orders/{id}/update")
    suspend fun updateWorkOrder(
        @Path("id") id: String,
        @Body request: UpdateWorkOrderRequest
    ): Response<WorkOrderDto>

    // ─── Agent Tasks ──────────────────────────────────────────────────────────

    @GET("agents/tasks")
    suspend fun getAgentTasks(): Response<AgentTasksListResponse>

    @POST("agents/tasks/{id}/acknowledge")
    suspend fun acknowledgeAgentTask(@Path("id") id: String): Response<AgentTaskDto>

    @POST("agents/tasks/{id}/complete")
    suspend fun completeAgentTask(
        @Path("id") id: String,
        @Body request: CompleteAgentTaskRequest
    ): Response<AgentTaskDto>

    // ─── Approvals ────────────────────────────────────────────────────────────

    @GET("approvals")
    suspend fun getApprovals(): Response<ApprovalsListResponse>

    @POST("approvals/{id}/decide")
    suspend fun decideApproval(
        @Path("id") id: String,
        @Body request: ApprovalDecisionRequest
    ): Response<ApprovalDto>

    // ─── Chat / Assistant ─────────────────────────────────────────────────────
    // Routes through backend to on-prem AI. No direct LLM/cloud calls from APK.

    @POST("chat")
    suspend fun sendMessage(@Body request: ChatRequest): Response<ChatResponse>

    // ─── SOP / Knowledge ──────────────────────────────────────────────────────

    @GET("knowledge/sop")
    suspend fun getSopList(): Response<SopListResponse>

    @GET("knowledge/sop/{id}")
    suspend fun getSop(@Path("id") id: String): Response<SopDto>

    // ─── Issues ───────────────────────────────────────────────────────────────

    @POST("issues")
    suspend fun reportIssue(@Body request: ReportIssueRequest): Response<IssueResponse>

    // ─── Evidence / Documents ─────────────────────────────────────────────────

    @Multipart
    @POST("documents/upload")
    suspend fun uploadEvidence(
        @Part file: MultipartBody.Part,
        @Part("equipment_id") equipmentId: okhttp3.RequestBody?,
        @Part("work_order_id") workOrderId: okhttp3.RequestBody?,
        @Part("caption") caption: okhttp3.RequestBody?
    ): Response<UploadEvidenceResponse>

    // ─── Notifications ────────────────────────────────────────────────────────

    @GET("notifications")
    suspend fun getNotifications(): Response<NotificationsListResponse>

    @POST("notifications/{id}/read")
    suspend fun markNotificationRead(@Path("id") id: String): Response<Unit>
}
