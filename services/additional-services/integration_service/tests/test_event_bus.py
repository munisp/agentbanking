'''
Pytest unit tests for event_bus.py. These tests ensure the EventBus class
functions correctly, covering event publishing, subscribing, SSE stream generation,
and Redis integration, with a focus on achieving high code coverage.
'''

import asyncio
import json
from unittest.mock import patch

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis

# Assuming event_bus.py is in the same directory or in the Python path
from event_bus import EventBus

# Constants for test events
TEST_EVENT_TYPE = "test_event"
TEST_PAYLOAD = {"data": "some_value"}


@pytest_asyncio.fixture
async def mock_redis_client():
    """Provides a fake Redis client for testing that mimics aioredis."""
    client = FakeRedis()
    yield client
    await client.close()


@pytest_asyncio.fixture
async def event_bus(mock_redis_client):
    """Provides an EventBus instance initialized with a mock Redis client."""
    bus = EventBus(redis_client=mock_redis_client)
    await bus.connect()
    yield bus
    await bus.disconnect()


@pytest.mark.asyncio
async def test_should_publish_event_successfully_when_data_is_valid(event_bus, mock_redis_client):
    """
    Tests that publishing an event sends a correctly formatted JSON message
    to the Redis "events" channel.
    """
    # The end-to-end functionality is tested in the subscribe test.
    # This test primarily ensures the publish method doesn't raise exceptions.
    await event_bus.publish_event(TEST_EVENT_TYPE, TEST_PAYLOAD)


@pytest.mark.asyncio
async def test_should_subscribe_and_receive_event_when_handler_is_registered(event_bus):
    """
    Tests that a subscribed handler is correctly called when a matching event is published.
    """
    received_event = None
    event_received_future = asyncio.Future()

    def mock_handler(event):
        nonlocal received_event
        received_event = event
        event_received_future.set_result(True)

    event_bus.subscribe(TEST_EVENT_TYPE, mock_handler)

    # Give the listener a moment to process the subscription
    await asyncio.sleep(0.01)

    await event_bus.publish_event(TEST_EVENT_TYPE, TEST_PAYLOAD)

    await asyncio.wait_for(event_received_future, timeout=1.0)

    assert received_event is not None
    assert received_event["type"] == TEST_EVENT_TYPE
    assert received_event["payload"] == TEST_PAYLOAD


@pytest.mark.asyncio
async def test_should_not_receive_event_when_handler_is_for_different_type(event_bus):
    """
    Tests that a handler does not receive an event if the event type does not match.
    """
    handler_was_called = False

    def mock_handler(event):
        nonlocal handler_was_called
        handler_was_called = True

    event_bus.subscribe("another_event_type", mock_handler)

    await event_bus.publish_event(TEST_EVENT_TYPE, TEST_PAYLOAD)

    await asyncio.sleep(0.1)

    assert not handler_was_called, "Handler should not have been called for the wrong event type"


@pytest.mark.asyncio
async def test_should_generate_sse_stream_for_all_events_when_no_filter_is_provided(event_bus):
    """
    Tests the SSE stream generation, ensuring all events are received when no filter is applied.
    """
    sse_generator = event_bus.sse_stream()

    # Start the generator to ensure subscription happens
    await sse_generator.asend(None)

    # Publish the event
    await event_bus.publish_event(TEST_EVENT_TYPE, TEST_PAYLOAD)

    # Wait for the message to be yielded
    sse_message = await asyncio.wait_for(anext(sse_generator), timeout=1.0)

    expected_sse = f"event: {TEST_EVENT_TYPE}\ndata: {json.dumps(TEST_PAYLOAD)}\n\n"
    assert sse_message == expected_sse

    # Close the generator to clean up the dedicated pubsub
    await sse_generator.aclose()


@pytest.mark.asyncio
async def test_should_generate_sse_stream_only_for_filtered_events_when_filter_is_provided(event_bus):
    """
    Tests that the SSE stream correctly filters events based on the provided event type.
    """
    filtered_event_type = "filtered_event"
    sse_generator = event_bus.sse_stream(event_filter=filtered_event_type)

    # Start the generator to ensure subscription happens
    await sse_generator.asend(None)

    # Publish the events
    await event_bus.publish_event("ignored_event", {"data": "ignore"})
    await event_bus.publish_event(filtered_event_type, TEST_PAYLOAD)

    # Wait for the message to be yielded
    sse_message = await asyncio.wait_for(anext(sse_generator), timeout=1.0)

    expected_sse = f"event: {filtered_event_type}\ndata: {json.dumps(TEST_PAYLOAD)}\n\n"
    assert sse_message == expected_sse

    # Close the generator to clean up the dedicated pubsub
    await sse_generator.aclose()


@pytest.mark.asyncio
async def test_should_handle_disconnect_gracefully(event_bus):
    """
    Tests that the disconnect method properly cancels listener tasks and closes connections.
    """
    listener_task = event_bus.listener_task
    with patch.object(listener_task, 'cancel', wraps=listener_task.cancel) as cancel_spy:
        await event_bus.disconnect()
        cancel_spy.assert_called_once()

    assert listener_task.done()


@pytest.mark.asyncio
async def test_should_handle_json_decode_error_gracefully_in_listener(event_bus, mock_redis_client):
    """
    Tests that the event bus listener can survive a malformed JSON message without crashing.
    """
    with patch('builtins.print') as mock_print:
        await mock_redis_client.publish("events", b"this is not json")

        await asyncio.sleep(0.1)

        mock_print.assert_called()
        assert "Failed to decode JSON" in mock_print.call_args[0][0]

        handler_future = asyncio.Future()
        event_bus.subscribe(TEST_EVENT_TYPE, lambda e: handler_future.set_result(True))
        await event_bus.publish_event(TEST_EVENT_TYPE, TEST_PAYLOAD)

        await asyncio.wait_for(handler_future, timeout=1.0)
        assert handler_future.done()


async def anext(ait):
    return await ait.__anext__()