<!-- dli-course-cell {"id":"3-Prompting-With-Messages/30-Section-Introduction:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"0ed8ff2b152fda792ae2543f01dee5534e2db79bf64c354b834a1dc6718b767d","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Section 3: Prompting With Messages</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/30-Section-Introduction:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"65997bdb56ba8f15655d4ca327f072de0d1f2222d54e8b71f33e65c9edb9c7b7","type":"markdown"} -->
Thus far our interactions with our chat model have been text in text out. In this section we'll begin by exposing that behind the text are indications of the role of who is providing the text (human or AI) and will learn how to author prompts that explicitly use these and other available roles to great effect.

By the time you complete this section you will be able to employ few-shot prompting, utilize the system message to define the overarching role or persona of a chatbot, and be able to get your chat model to tackle tasks that may have otherwise been too complex for it by using a technique called chain-of-thought prompting.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/30-Section-Introduction:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/30-Section-Introduction:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7195870e33f28b717ecdc318a3d85fd351fe251a04efdf50fd61ea77593392fc","type":"markdown"} -->
## Section Table of Contents
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"3-Prompting-With-Messages/30-Section-Introduction:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"a76ad761b8ad88de61f9691650d78d3255d7459dabd5246403cbc9f4f46f7f68","type":"markdown"} -->
1. **Human and AI Messages:** In this notebook you'll learn about two of the core chat message types, human and AI messages, and how to use them explictly in application code.
2. **Few-Shot Prompting:** In this notebook you'll learn how to provide chat models with instructive examples by way of a technique called few-shot prompting.
3. **System Message:** In this notebook you'll learn about the system message, which will allow you to define an overarching persona and role for your chat models.
4. **Chain-of-Thought Prompting:** In this notebook, you will learn about one of the most famous prompting techniques called Chain-of-Thought prompting.
5. **Reasoning Models:** In this notebook, you will explore reasoning models, LLMs trained for step-by-step deliberation, and learn how to work with their thinking tokens.
6. **Chatbots:** In this notebook, you will learn how to manage messages to retain conversation history and enable chatbot functionality.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>3-Prompting-With-Messages/31-Human-and-AI-Messages.ipynb</code> next: <strong>Human and AI Messages</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Pick one place where role separation should make the prompt easier to steer, because the next notebook turns that idea into explicit message objects.</p>
</div>
<!-- /dli-course-cell -->
