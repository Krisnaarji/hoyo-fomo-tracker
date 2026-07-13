package com.nasana.hoyofomotracker

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AppPrefsTest {

    // Uses device-protected storage so this never touches the app's real
    // SharedPreferences (which defaults to Krisna's real backend URL).
    private val context = InstrumentationRegistry.getInstrumentation()
        .targetContext
        .createDeviceProtectedStorageContext()

    @Before
    fun clearPrefs() {
        context.getSharedPreferences("hoyo_fomo_prefs", android.content.Context.MODE_PRIVATE)
            .edit()
            .clear()
            .commit()
    }

    @After
    fun tearDown() {
        clearPrefs()
    }

    @Test
    fun getBaseUrl_defaultsWhenNeverSet() {
        assertEquals(AppPrefs.DEFAULT_BASE_URL, AppPrefs.getBaseUrl(context))
    }

    @Test
    fun setBaseUrl_persistsAndRoundTrips() {
        AppPrefs.setBaseUrl(context, "http://10.0.2.2:8199")
        assertEquals("http://10.0.2.2:8199", AppPrefs.getBaseUrl(context))
    }

    @Test
    fun getWidgetLimit_defaultsWhenNeverSet() {
        assertEquals(AppPrefs.DEFAULT_WIDGET_LIMIT, AppPrefs.getWidgetLimit(context))
    }

    @Test
    fun setWidgetLimit_persistsAndRoundTrips() {
        AppPrefs.setWidgetLimit(context, 25)
        assertEquals(25, AppPrefs.getWidgetLimit(context))
    }

    @Test
    fun getNotificationsEnabled_defaultsToTrue() {
        assertTrue(AppPrefs.getNotificationsEnabled(context))
    }

    @Test
    fun setNotificationsEnabled_persistsAndRoundTrips() {
        AppPrefs.setNotificationsEnabled(context, false)
        assertEquals(false, AppPrefs.getNotificationsEnabled(context))
    }
}
