<!-- dli-course-cell {"id":"5-Tools/50-Section-Introduction:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"4753b6daaa82c8682aeef0d8ca82edccfe3002f2fb7d712aaab15e2d5b838627","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Section 5: Tool Use and Agents</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"5-Tools/50-Section-Introduction:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"820672a7717168e24e06d1d463ebaa0d846f17598209051a1f5a613559f077b3","type":"markdown"} -->
LLMs can identify when and how it should utilize external interfaces outside of its own model priors. Such components of functionality external to the LLM are referred to as tools, and the paradigm by which our LLM-applications identify when and how to use tools is called agents.

Tool use and agents are a huge topic in their own right, but in this section we'd like to give you an introduction to their use in the context of LLM applications. By the time you complete this section you be able to create tools, as well as simple agents that can integrate their use into your LLM-based chains.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"5-Tools/50-Section-Introduction:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"5-Tools/50-Section-Introduction:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7195870e33f28b717ecdc318a3d85fd351fe251a04efdf50fd61ea77593392fc","type":"markdown"} -->
## Section Table of Contents
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"5-Tools/50-Section-Introduction:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"a500aec6227074be099d842e1517955b31b2754f2cd355807c920c2655362b46","type":"markdown"} -->
1. **Tool Calling:** In this notebook you learn to create tools, and make your LLM instances aware of their availability for use.
2. **Agents:** In this notebook you will learn how to create an agent capable of reasoning about when tool use is appropriate, and integrating the result of tool use into its responses.
3. **Workshop Conclusion:** In this final notebook we conclude the workshop with a summary of all you've done, instructions for getting a certificate for the workshop, a request for feedback, and recommendations for next steps.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>5-Tools/51-Tool-Calling.ipynb</code> next: <strong>Tool Calling</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Pick one external capability your workflow needs, because the next notebook makes that dependency visible as a tool interface instead of hidden logic.</p>
</div>
<!-- /dli-course-cell -->
