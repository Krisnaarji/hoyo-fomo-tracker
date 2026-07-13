package com.nasana.hoyofomotracker

import android.content.Context

object AppPrefs {
    private const val PREFS_NAME = "hoyo_fomo_prefs"
    private const val KEY_BASE_URL = "base_url"
    private const val KEY_WIDGET_LIMIT = "widget_limit"
    private const val KEY_NOTIFICATIONS_ENABLED = "notifications_enabled"

    const val DEFAULT_BASE_URL = "http://100.96.16.97:8123"
    const val DEFAULT_WIDGET_LIMIT = 5

    fun getBaseUrl(context: Context): String =
        prefs(context).getString(KEY_BASE_URL, DEFAULT_BASE_URL) ?: DEFAULT_BASE_URL

    fun setBaseUrl(context: Context, value: String) {
        prefs(context).edit().putString(KEY_BASE_URL, value).apply()
    }

    fun getWidgetLimit(context: Context): Int =
        prefs(context).getInt(KEY_WIDGET_LIMIT, DEFAULT_WIDGET_LIMIT)

    fun setWidgetLimit(context: Context, value: Int) {
        prefs(context).edit().putInt(KEY_WIDGET_LIMIT, value).apply()
    }

    fun getNotificationsEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_NOTIFICATIONS_ENABLED, true)

    fun setNotificationsEnabled(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_NOTIFICATIONS_ENABLED, value).apply()
    }

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
}
