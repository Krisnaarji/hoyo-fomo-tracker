package com.nasana.hoyofomotracker

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class HoyoApiTest {

    private fun rootWithEvents(vararg events: JSONObject): JSONObject {
        val game = JSONObject()
            .put("game_title", "TestGame")
            .put("events", org.json.JSONArray(events.toList()))

        return JSONObject().put("games", org.json.JSONArray(listOf(game)))
    }

    private fun event(
        name: String,
        category: String,
        daysLeft: Int?,
        action: JSONObject?
    ): JSONObject {
        val e = JSONObject()
            .put("event_name", name)
            .put("emoji", "X")
            .put("category_tag", category)
            .put("days_left", daysLeft ?: JSONObject.NULL)

        if (action != null) {
            e.put("action", action)
        }

        return e
    }

    private fun singleTapAction(label: String = "Do it") =
        JSONObject().put("endpoint", "/x").put("method", "POST").put("label", label)

    private fun heavyAction() =
        JSONObject().put("endpoint", "/x").put("method", "PATCH")
            .put("body_options", org.json.JSONArray(listOf(25, 50, 75, 100)))

    @Test
    fun findTopSingleTapEvent_prefersDailyOverSpeedrun() {
        val root = rootWithEvents(
            event("Speedy", "SPEEDRUN", 1, singleTapAction()),
            event("Checkin", "DAILY", null, singleTapAction())
        )

        val result = HoyoApi.findTopSingleTapEvent(root)

        assertEquals("Checkin", result?.first?.getString("event_name"))
    }

    @Test
    fun findTopSingleTapEvent_breaksTiesByDaysLeft() {
        val root = rootWithEvents(
            event("Far speedrun", "SPEEDRUN", 10, singleTapAction()),
            event("Near speedrun", "SPEEDRUN", 1, singleTapAction())
        )

        val result = HoyoApi.findTopSingleTapEvent(root)

        assertEquals("Near speedrun", result?.first?.getString("event_name"))
    }

    @Test
    fun findTopSingleTapEvent_excludesHeavyActions() {
        val root = rootWithEvents(
            event("Heavy one", "HEAVY", 0, heavyAction())
        )

        val result = HoyoApi.findTopSingleTapEvent(root)

        assertNull(result)
    }

    @Test
    fun findTopSingleTapEvent_nullWhenNoActionableEvents() {
        val root = rootWithEvents(
            event("Nothing to do", "DAILY", null, null)
        )

        val result = HoyoApi.findTopSingleTapEvent(root)

        assertNull(result)
    }

    @Test
    fun findTopHeavyEvent_picksLowestDaysLeft() {
        val root = rootWithEvents(
            event("Far heavy", "HEAVY", 12, heavyAction()),
            event("Near heavy", "HEAVY", 0, heavyAction())
        )

        val result = HoyoApi.findTopHeavyEvent(root)

        assertEquals("Near heavy", result?.first?.getString("event_name"))
    }

    @Test
    fun findTopHeavyEvent_ignoresSingleTapActions() {
        val root = rootWithEvents(
            event("Speedy", "SPEEDRUN", 0, singleTapAction()),
            event("Daily", "DAILY", null, singleTapAction())
        )

        val result = HoyoApi.findTopHeavyEvent(root)

        assertNull(result)
    }

    @Test
    fun findTopHeavyEvent_treatsNullDaysLeftAsLowestPriority() {
        val root = rootWithEvents(
            event("No end date", "HEAVY", null, heavyAction()),
            event("Ending soon", "HEAVY", 3, heavyAction())
        )

        val result = HoyoApi.findTopHeavyEvent(root)

        assertEquals("Ending soon", result?.first?.getString("event_name"))
    }

    @Test
    fun findTopHeavyEvent_selectsSoleCandidateWithNullDaysLeft() {
        val root = rootWithEvents(
            event("Open-ended lore event", "HEAVY", null, heavyAction())
        )

        val result = HoyoApi.findTopHeavyEvent(root)

        assertEquals("Open-ended lore event", result?.first?.getString("event_name"))
    }

    @Test
    fun findTopSingleTapEvent_nullWhenNoEventsAtAll() {
        val root = rootWithEvents()

        val result = HoyoApi.findTopSingleTapEvent(root)

        assertNull(result)
    }

    @Test
    fun findTopHeavyEvent_nullWhenNoEventsAtAll() {
        val root = rootWithEvents()

        val result = HoyoApi.findTopHeavyEvent(root)

        assertNull(result)
    }
}
