package com.nasana.hoyofomotracker

import android.app.NotificationManager
import android.content.Context
import androidx.core.app.NotificationCompat
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetAddress
import java.net.ServerSocket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

@RunWith(AndroidJUnit4::class)
class HoyoReminderWorkerTest {

    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val prefs = context.getSharedPreferences("hoyo_fomo_prefs", Context.MODE_PRIVATE)

    private var hadOriginalBaseUrl = false
    private var originalBaseUrl: String? = null

    @Before
    fun setUp() {
        hadOriginalBaseUrl = prefs.contains("base_url")
        originalBaseUrl = prefs.getString("base_url", null)

        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            android.app.NotificationChannel(
                HoyoReminderWorker.CHANNEL_ID,
                "HoYo FOMO Reminders",
                NotificationManager.IMPORTANCE_DEFAULT
            )
        )
    }

    @After
    fun restoreBaseUrl() {
        if (hadOriginalBaseUrl) {
            prefs.edit().putString("base_url", originalBaseUrl).commit()
        } else {
            prefs.edit().remove("base_url").commit()
        }
    }

    /** Minimal single-request HTTP server so this test has zero external dependencies. */
    private class CapturingHttpServer {
        data class CapturedRequest(val method: String, val path: String, val body: String)

        private val socket = ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))
        private val latch = CountDownLatch(1)
        @Volatile var captured: CapturedRequest? = null
            private set

        val port: Int get() = socket.localPort

        fun startAcceptingOneRequest() {
            Thread {
                socket.accept().use { client ->
                    val reader = BufferedReader(InputStreamReader(client.getInputStream()))
                    val requestLine = reader.readLine() ?: ""
                    val (method, path) = requestLine.split(" ").let { it.getOrElse(0) { "" } to it.getOrElse(1) { "" } }

                    var contentLength = 0
                    var line: String?
                    while (true) {
                        line = reader.readLine()
                        if (line.isNullOrEmpty()) break
                        if (line.startsWith("Content-Length:", ignoreCase = true)) {
                            contentLength = line.substringAfter(":").trim().toIntOrNull() ?: 0
                        }
                    }

                    val bodyChars = CharArray(contentLength)
                    if (contentLength > 0) reader.read(bodyChars, 0, contentLength)

                    captured = CapturedRequest(method, path, String(bodyChars))

                    val responseBody = "{\"ok\":true}"
                    client.getOutputStream().write(
                        (
                            "HTTP/1.1 200 OK\r\n" +
                                "Content-Type: application/json\r\n" +
                                "Content-Length: ${responseBody.length}\r\n" +
                                "Connection: close\r\n\r\n" +
                                responseBody
                            ).toByteArray()
                    )
                }
                latch.countDown()
            }.start()
        }

        fun awaitRequest(timeoutSeconds: Long = 5): Boolean = latch.await(timeoutSeconds, TimeUnit.SECONDS)

        fun close() = socket.close()
    }

    private fun heavyOnlyRoot(eventId: Int = 13): JSONObject {
        val action = JSONObject()
            .put("endpoint", "/events/$eventId/progress")
            .put("method", "PATCH")
            .put("body_options", JSONArray(listOf(25, 50, 75, 100)))

        val event = JSONObject()
            .put("event_name", "Cyclical Extrapolation")
            .put("emoji", "🔥")
            .put("category_tag", "HEAVY")
            .put("days_left", 0)
            .put("action", action)

        val game = JSONObject()
            .put("game_title", "HSR")
            .put("events", JSONArray(listOf(event)))

        return JSONObject()
            .put("today", "2026-07-14")
            .put("total_actions", 1)
            .put("hidden_actions", 0)
            .put("games", JSONArray(listOf(game)))
    }

    private fun dailyOnlyRoot(): JSONObject {
        val action = JSONObject()
            .put("endpoint", "/events/7/daily-checkin")
            .put("method", "POST")
            .put("label", "Check-in")

        val event = JSONObject()
            .put("event_name", "Gift of Odyssey")
            .put("emoji", "🎁")
            .put("category_tag", "DAILY")
            .put("days_left", 0)
            .put("action", action)

        val game = JSONObject()
            .put("game_title", "HSR")
            .put("events", JSONArray(listOf(event)))

        return JSONObject()
            .put("today", "2026-07-14")
            .put("total_actions", 1)
            .put("hidden_actions", 0)
            .put("games", JSONArray(listOf(game)))
    }

    @Test
    fun heavyOnly_notificationNamesEventAndHasThreeProgressActions() {
        val notification = HoyoReminderWorker.buildReminderNotification(context, heavyOnlyRoot(), 1)

        val text = notification.extras.getCharSequence(NotificationCompat.EXTRA_TEXT).toString()
        assertTrue(text.contains("Cyclical Extrapolation"))

        val actions = notification.actions ?: emptyArray()
        assertEquals(3, actions.size)
        assertEquals(listOf("25%", "50%", "Done"), actions.map { it.title.toString() })
    }

    @Test
    fun dailyOnly_notificationUsesSingleTapActionNotHeavyBranch() {
        val notification = HoyoReminderWorker.buildReminderNotification(context, dailyOnlyRoot(), 1)

        val text = notification.extras.getCharSequence(NotificationCompat.EXTRA_TEXT).toString()
        assertTrue(text.contains("Gift of Odyssey"))

        val actions = notification.actions ?: emptyArray()
        assertEquals(1, actions.size)
        assertEquals("Check-in", actions[0].title.toString())
    }

    @Test
    fun heavyDoneAction_firesRealPatchAgainstSelfContainedFixture() {
        val server = CapturingHttpServer()
        try {
            server.startAcceptingOneRequest()
            // This server runs in-process on the device/emulator itself (same
            // as the app under test), so it's reached via the device's own
            // loopback - not the 10.0.2.2 host-alias used elsewhere for
            // reaching a server running on the Windows host.
            val fixtureUrl = "http://127.0.0.1:${server.port}"
            prefs.edit().putString("base_url", fixtureUrl).commit()

            val notification = HoyoReminderWorker.buildReminderNotification(
                context,
                heavyOnlyRoot(eventId = 2),
                1
            )
            val doneAction = (notification.actions ?: emptyArray()).last()
            assertEquals("Done", doneAction.title.toString())

            // Sending the action's PendingIntent directly exercises the exact
            // same NotificationActionReceiver -> HoyoApi.runAction path a real
            // tap would, with zero risk since this fixture is local-only.
            doneAction.actionIntent.send()

            assertTrue("Fixture server never received a request", server.awaitRequest())

            val request = server.captured!!
            assertEquals("PATCH", request.method)
            assertEquals("/events/2/progress", request.path)
            assertEquals(JSONObject(request.body).getInt("progress_status"), 100)
        } finally {
            server.close()
        }
    }
}
