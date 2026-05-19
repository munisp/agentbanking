package com.pos54link.app

import com.pos54link.app.viewmodels.TransactionViewModel
import com.pos54link.app.viewmodels.TransactionUiState
import com.pos54link.app.data.api.TransactionService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.mockito.kotlin.*

/**
 * Unit tests for TransactionViewModel using coroutines test dispatcher.
 * Mocks TransactionService to isolate ViewModel logic.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class TransactionViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var mockService: TransactionService
    private lateinit var viewModel: TransactionViewModel

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        mockService = mock()
        viewModel = TransactionViewModel(mockService)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `initial state is idle`() {
        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertNull(state.error)
        assertNull(state.successRef)
    }

    @Test
    fun `processCashIn sets loading then success`() = runTest {
        val fakeResult = mock<TransactionService.TxResult> {
            on { reference } doReturn "TXN-001"
        }
        whenever(mockService.cashIn(any(), any(), any())).thenReturn(fakeResult)

        viewModel.processCashIn("08012345678", 5000.0, "Test cash in")
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertEquals("TXN-001", state.successRef)
        assertNull(state.error)
    }

    @Test
    fun `processCashIn sets error on exception`() = runTest {
        whenever(mockService.cashIn(any(), any(), any())).thenThrow(RuntimeException("Network error"))

        viewModel.processCashIn("08012345678", 5000.0, "Test")
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertNull(state.successRef)
        assertEquals("Network error", state.error)
    }

    @Test
    fun `processCashOut sets success ref on success`() = runTest {
        val fakeResult = mock<TransactionService.TxResult> {
            on { reference } doReturn "TXN-002"
        }
        whenever(mockService.cashOut(any(), any(), any())).thenReturn(fakeResult)

        viewModel.processCashOut("08012345678", 2000.0, "WD-1234")
        advanceUntilIdle()

        assertEquals("TXN-002", viewModel.uiState.value.successRef)
    }

    @Test
    fun `processBillPayment sets success ref on success`() = runTest {
        val fakeResult = mock<TransactionService.TxResult> {
            on { reference } doReturn "TXN-003"
        }
        whenever(mockService.billPayment(any(), any(), any(), any())).thenReturn(fakeResult)

        viewModel.processBillPayment("electricity", "EKEDC", "12345678901", 10000.0)
        advanceUntilIdle()

        assertEquals("TXN-003", viewModel.uiState.value.successRef)
    }

    @Test
    fun `clearSuccess resets successRef`() = runTest {
        val fakeResult = mock<TransactionService.TxResult> {
            on { reference } doReturn "TXN-004"
        }
        whenever(mockService.cashIn(any(), any(), any())).thenReturn(fakeResult)

        viewModel.processCashIn("08012345678", 1000.0, "")
        advanceUntilIdle()

        assertNotNull(viewModel.uiState.value.successRef)
        viewModel.clearSuccess()
        assertNull(viewModel.uiState.value.successRef)
    }

    @Test
    fun `requestPinPadVerification calls onVerified on success`() = runTest {
        whenever(mockService.verifyPinPad(any(), any())).thenReturn(true)

        var verified = false
        var failed = false
        viewModel.requestPinPadVerification(
            phone = "08012345678",
            amount = 5000.0,
            onVerified = { verified = true },
            onFailed = { failed = true }
        )
        advanceUntilIdle()

        assertTrue(verified)
        assertFalse(failed)
    }

    @Test
    fun `requestPinPadVerification calls onFailed on false response`() = runTest {
        whenever(mockService.verifyPinPad(any(), any())).thenReturn(false)

        var verified = false
        var failed = false
        viewModel.requestPinPadVerification(
            phone = "08012345678",
            amount = 5000.0,
            onVerified = { verified = true },
            onFailed = { failed = true }
        )
        advanceUntilIdle()

        assertFalse(verified)
        assertTrue(failed)
    }
}
