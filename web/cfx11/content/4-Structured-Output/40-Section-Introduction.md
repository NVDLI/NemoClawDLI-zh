<!-- dli-course-cell {"id":"4-Structured-Output/40-Section-Introduction:0","index":0,"schema":"dli-course-cell/1.0","source_sha256":"497fec0442a6a3e81a22e5b544b06b93de9c7c23fb8abdae8b08b1b2d9b6748d","type":"markdown"} -->
<br>
<a href="https://www.nvidia.com/en-us/training/">
    <div style="width: 55%; background-color: white; margin-top: 50px;">
    <img src="https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png"
         width="400"
         height="186"
         style="margin: 0px -25px -5px; width: 300px"/></div>
</a>
<h1 style="line-height: 1.4;"><font color="#76b900"><b>Building LLM Applications With Prompt Engineering</b></font></h1>
<h2><b>Section 4: Structured Output</b></h2>
<br>
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"4-Structured-Output/40-Section-Introduction:1","index":1,"schema":"dli-course-cell/1.0","source_sha256":"ad7a73747aef191aa2c44ce767795fa450a11e213d3bfb6ad6d81c8e5b9da1cc","type":"markdown"} -->
In this section, you'll learn the difference between getting JSON and getting a dependable application contract. The model used in this course is already strong at producing clean JSON, so the interesting work shifts to sharper questions: did the output use the right fields, did it preserve the intended meaning, can a downstream parser trust it, and what happens when the document is long or ambiguous? You'll use Pydantic and LangChain parsers to turn strong model behavior into validation you can actually depend on.
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"4-Structured-Output/40-Section-Introduction:2","index":2,"schema":"dli-course-cell/1.0","source_sha256":"cb3f91d54eee30e53e35b2b99905f70f169ed549fd78909d3dac2defc9ed8d3b","type":"markdown"} -->
---
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"4-Structured-Output/40-Section-Introduction:3","index":3,"schema":"dli-course-cell/1.0","source_sha256":"7195870e33f28b717ecdc318a3d85fd351fe251a04efdf50fd61ea77593392fc","type":"markdown"} -->
## Section Table of Contents
<!-- /dli-course-cell -->

<!-- dli-course-cell {"id":"4-Structured-Output/40-Section-Introduction:4","index":4,"schema":"dli-course-cell/1.0","source_sha256":"337c144fbf5d69afc056431967c3b466cb4e41f0a7eba3d1c57b311eb2f0d909","type":"markdown"} -->
1. **Structured Output:** In this notebook we introduce using LLMs to generate structured output, and explore some basic methods for using LLMs to generate data in batch for downstream use.
2. **Structured Output With Pydantic:** In this notebook you will drastically upgrade your ability to generate structured output through a combination of Pydantic classes and LangChain's `JsonOutputParser`.
3. **Document Tagging:** In this notebook you'll extend your skill set of generating structured data by learning how to efficiently extract data and and synthesize tags from long-form text documents.

---

<!-- NEXT_STEP_CARD -->

<div style="border-left: 6px solid #76B900; background: #f7fdf2; padding: 14px 18px; border-radius: 10px; margin: 20px 0;">
<p style="margin: 0 0 6px; color: #315c00; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;">Continue the unified course path</p>
<p style="margin: 0 0 8px; color: black;"><strong>Next step:</strong> Open <code>4-Structured-Output/41-Structured-Output.ipynb</code> next: <strong>Structured Output</strong>.</p>
<p style="margin: 0; color: black;"><strong>Before moving on:</strong> Choose one downstream task that needs predictable fields instead of prose, because the next notebook makes that contract explicit.</p>
</div>
<!-- /dli-course-cell -->
