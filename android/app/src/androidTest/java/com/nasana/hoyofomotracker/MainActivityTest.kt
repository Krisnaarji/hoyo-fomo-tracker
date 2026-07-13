package com.nasana.hoyofomotracker

import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.action.ViewActions.clearText
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.action.ViewActions.closeSoftKeyboard
import androidx.test.espresso.action.ViewActions.typeText
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.matcher.ViewMatchers.withHint
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.WorkManager
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class MainActivityTest {

    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    // Deliberately unroutable/closed so MainActivity's auto-fetch-on-launch
    // (a real network call to AppPrefs.getBaseUrl()) can never reach any
    // real backend, including production, no matter what this test does.
    private val safeUnreachableUrl = "http://127.0.0.1:1"

    @Before
    fun setUp() {
        AppPrefs.setBaseUrl(context, safeUnreachableUrl)
        AppPrefs.setWidgetLimit(context, 5)
        AppPrefs.setNotificationsEnabled(context, false)
        AppPrefs.setSetupConfirmed(context, true)
    }

    @After
    fun tearDown() {
        // Valid-save tests call HoyoApplication.scheduleReminderWork(), which
        // schedules a real persistent WorkManager job - clearing prefs alone
        // would leave that job behind. Cancel and wait for it before leaving.
        WorkManager.getInstance(context)
            .cancelUniqueWork("hoyo_reminder_check")
            .result
            .get()

        context.getSharedPreferences("hoyo_fomo_prefs", android.content.Context.MODE_PRIVATE)
            .edit()
            .clear()
            .commit()
    }

    @Test
    fun baseUrlField_prefilledWithCurrentPreference() {
        ActivityScenario.launch(MainActivity::class.java).use {
            onView(withHint("Base API URL")).check(matches(withText(safeUnreachableUrl)))
        }
    }

    @Test
    fun widgetLimitField_prefilledWithCurrentPreference() {
        ActivityScenario.launch(MainActivity::class.java).use {
            onView(withHint("Widget item limit")).check(matches(withText("5")))
        }
    }

    @Test
    fun saveSettings_withInvalidLimit_doesNotPersistChange() {
        ActivityScenario.launch(MainActivity::class.java).use {
            onView(withHint("Widget item limit")).perform(clearText(), typeText("0"), closeSoftKeyboard())
            onView(withText("Save settings")).perform(click())
        }

        // Invalid input (limit <= 0) must be rejected, not persisted.
        assertEquals(5, AppPrefs.getWidgetLimit(context))
    }

    @Test
    fun saveSettings_withValidInput_persistsNewValues() {
        ActivityScenario.launch(MainActivity::class.java).use {
            onView(withHint("Widget item limit")).perform(clearText(), typeText("12"), closeSoftKeyboard())
            onView(withText("Save settings")).perform(click())
        }

        assertEquals(12, AppPrefs.getWidgetLimit(context))
    }

    @Test
    fun saveSettings_withValidInput_marksSetupConfirmed() {
        AppPrefs.setSetupConfirmed(context, false)

        ActivityScenario.launch(MainActivity::class.java).use {
            onView(withHint("Widget item limit")).perform(clearText(), typeText("5"), closeSoftKeyboard())
            onView(withText("Save settings")).perform(click())
        }

        assertEquals(true, AppPrefs.getSetupConfirmed(context))
    }
}
