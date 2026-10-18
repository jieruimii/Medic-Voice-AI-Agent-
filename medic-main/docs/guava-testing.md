> ## Documentation Index
> Fetch the complete documentation index at: https://docs.goguava.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Automated Testing for Guava Agents

> Test your agents end-to-end with your existing testing framework

<Tabs>
  <Tab title="Python">
    <Note>
      This guide focuses on automated testing. For manual testing, use `agent.call_local()` to place a test call using your local audio device, or `agent.chat()` to interact with your agent via text in the terminal.
    </Note>

    Guava Agent tests are defined in code. You can write them using your existing testing framework, such as `pytest` or Python's built-in `unittest` module. This lets you test your Agent end-to-end alongside your Expert's code, using patterns you're already familiar with.
  </Tab>

  <Tab title="TypeScript">
    <Note>
      This guide focuses on automated testing. For manual testing, use `agent.callLocal()` to place a test call using your local audio device, or `agent.chat()` to interact with your agent via text in the terminal.
    </Note>

    Guava Agent tests are defined in code. You can write them using your existing testing framework, such as Jest or Vitest. This lets you test your Agent end-to-end alongside your Expert's code, using patterns you're already familiar with.
  </Tab>
</Tabs>

## Test individual Agent handlers with `MockCall`

<Tabs>
  <Tab title="Python">
    The most basic way to test Guava Agents is to test individual handlers like `on_action_request` or `on_question`. You can do so by constructing a `guava.testing.MockCall` object and passing it in directly to the handler.

    ```python test_agent.py theme={null}
    import unittest
    from guava.testing import MockCall

    # Import a handler from the help desk example.
    from guava.examples.help_desk import on_action_request

    class TestHandlers(unittest.TestCase):
        def test_routes_to_sales(self):
            # We can directly invoke that handler with a mocked Call object.
            actions = on_action_request(MockCall(), "I want to buy a new sofa")
            self.assertEqual("sales", actions[0].key)
    ```
  </Tab>

  <Tab title="TypeScript">
    The most basic way to test Guava Agents is to test individual handlers like `onActionRequest` or `onQuestion`. You can do so by constructing a `MockCall` object and passing it in directly to the handler via `agent.handlers`.

    ```typescript agent.test.ts theme={null}
    import { MockCall } from "@guava-ai/guava-sdk";

    // Import the agent from the help-desk example.
    import { agent } from "@guava-ai/guava-sdk/examples/help-desk";

    test("routes to sales", async () => {
        // We can directly invoke that handler with a mocked Call object.
        const suggestion = await agent.handlers.onActionRequest(new MockCall(), "I want to buy a new sofa");
        expect(suggestion).toHaveProperty("key", "sales");
    });
    ```
  </Tab>
</Tabs>

## Run a roleplay session and analyze the result

<Tabs>
  <Tab title="Python">
    `agent.roleplay(prompt="...")` runs your agent against a separate LLM that improvises a conversation based on a prompt. The session runs to completion and returns a `TestSession` object you can assert against. As in a real call, your registered handlers will be invoked by the Agent.

    The returned session object contains the transcript, useful helpers that can be asserted against, and a `session.evaluate` function that evaluates the conversation against a rubric.

    ```python test_roleplay.py theme={null}
    import unittest

    # Import the agent from the help desk example.
    from guava.examples.help_desk import agent

    class TestHelpDeskAgent(unittest.TestCase):
        def test_purchase_roleplay(self):
            session = agent.roleplay("You are a caller who wants to buy a new dining table.")

            # Use session.get_transcript() to retrieve the session's transcript.
            print(session.get_transcript())

            # Use session.evaluate() to assess the Agent's performance against a rubric.
            session.evaluate(
                # These criteria must all be true.
                pass_criteria=["The agent identified itself as working for Clearfield Home & Living."],
                # These criteria must all be false.
                fail_criteria=["The agent directly offered to search the inventory."],
            )

            # You can assert some values directly on the session object.
            self.assertIn("sales", session.executed_actions)
            self.assertEqual("bot-transfer", session.termination_reason)
    ```
  </Tab>

  <Tab title="TypeScript">
    `agent.roleplay(prompt)` runs your agent against a separate LLM that improvises a conversation based on a prompt. The session runs to completion and returns a `TestSession` object you can assert against. As in a real call, your registered handlers will be invoked by the Agent.

    The returned session object contains the transcript, useful helpers that can be asserted against, and a `session.evaluate()` function that evaluates the conversation against a rubric.

    ```typescript roleplay.test.ts theme={null}
    import { agent } from "@guava-ai/guava-sdk/examples/help-desk";

    test("purchase roleplay", async () => {
        const session = await agent.roleplay("You are a caller who wants to buy a new dining table.");

        // Use session.getTranscript() to retrieve the session's transcript.
        console.log(session.getTranscript());

        // Use session.evaluate() to assess the Agent's performance against a rubric.
        await session.evaluate({
            // These criteria must all be true.
            passCriteria: ["The agent identified itself as working for Clearfield Home & Living."],
            // These criteria must all be false.
            failCriteria: ["The agent directly offered to search the inventory."],
        });

        // You can assert some values directly on the session object.
        expect(session.executedActions).toContain("sales");
        expect(session.terminationReason).toBe("bot-transfer");
    });
    ```
  </Tab>
</Tabs>

## Patch Agent handlers before testing

In some cases, you may not want every handler to run during a test.
Use `agent.patch()` to create a clone of the Agent where you can override callbacks without modifying the original Agent.

<Tabs>
  <Tab title="Python">
    ```python test_patched_agent.py theme={null}
    import unittest
    import guava

    # Import the agent from the help desk example.
    from guava.examples.help_desk import agent

    class TestHelpDeskAgent(unittest.TestCase):
        def test_sales_closed(self):
            # Create a clone of the agent and patch the on_action handler.
            patched = agent.patch()

            @patched.on_action("sales")
            def patched_sales(call: guava.Call):
                call.hangup(
                    "Tell the caller that the sales department is closed and that "
                    "they should call back tomorrow between 9am and 5pm."
                )

            # Run the roleplay test with our patched agent.
            session = patched.roleplay("You are a caller who wants to buy a new dining table.")
            session.evaluate(["The agent informed the caller of the business hours from 9am to 5pm."])
    ```

    For any function that isn't an Agent handler, you can patch it using [Python's builtin patching system](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.patch).
  </Tab>

  <Tab title="TypeScript">
    ```typescript patched_agent.test.ts theme={null}
    import type { Call } from "@guava-ai/guava-sdk";
    import { agent } from "@guava-ai/guava-sdk/examples/help-desk";

    test("sales closed", async () => {
        // Create a clone of the agent and patch the onAction handler.
        const patched = agent.patch();

        patched.onAction("sales", async (call: Call) => {
            call.hangup(
                "Tell the caller that the sales department is closed and that " +
                "they should call back tomorrow between 9am and 5pm."
            );
        });

        // Run the roleplay test with our patched agent.
        const session = await patched.roleplay("You are a caller who wants to buy a new dining table.");
        await session.evaluate({
            passCriteria: ["The agent informed the caller of the business hours from 9am to 5pm."],
        });
    });
    ```

    For any function that isn't an Agent handler, you can patch it using your framework's built-in mocking tools.
  </Tab>
</Tabs>

## Run a session with full control

`agent.test()` gives you a live test session where you have full control over timing and caller utterances.
Use this when you need precise control over how the conversation unfolds.

<Tabs>
  <Tab title="Python">
    ```python test_help_desk.py theme={null}
    import unittest

    # Import the agent from the help desk example.
    from guava.examples.help_desk import agent

    class TestHelpDeskAgent(unittest.TestCase):
        def test_purchase_routes_to_sales(self):
            with agent.test() as session:
                # Wait until the agent has finished its opening turn.
                session.wait_for_turn()

                # Inject a caller utterance and let the agent respond.
                session.say("Hi, I'm looking to make a new purchase.")

                # Wait until the session ends (transfer, hangup, etc.).
                session.wait_for_end()

            # The TestSession here is the same type as those returned from roleplay sessions.
            # Assert against any of its values, read the transcript, or use 'session.evaluate(...)'
            self.assertIn("sales", session.executed_actions)
            self.assertEqual("bot-transfer", session.termination_reason)
    ```
  </Tab>

  <Tab title="TypeScript">
    ```typescript help_desk.test.ts theme={null}
    import { agent } from "@guava-ai/guava-sdk/examples/help-desk";

    test("purchase routes to sales", async () => {
        const session = await agent.test(async (session) => {
            // Wait until the agent has finished its opening turn.
            await session.waitForTurn();

            // Inject a caller utterance and let the agent respond.
            session.say("Hi, I'm looking to make a new purchase.");

            // Wait until the session ends (transfer, hangup, etc.).
            await session.waitForEnd();
        });

        // The TestSession here is the same type as those returned from roleplay sessions.
        // Assert against any of its values, read the transcript, or use 'session.evaluate(...)'
        expect(session.executedActions).toContain("sales");
        expect(session.terminationReason).toBe("bot-transfer");
    });
    ```
  </Tab>
</Tabs>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.