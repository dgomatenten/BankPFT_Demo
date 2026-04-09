

*(I also went ahead and fixed the accidental `#w` typo you generated at the end of the second prompt document!)*

To answer your question: **Data Model Design & Implementation is Prompt 3!**

Right after the AI has laid down the Application Factory (Prompt 1) and the UI Shell / Authentication (Prompt 2), it is perfectly primed to absorb your core database relational models.

Here is exactly how you should structure the third prompt:

***

### 🛠️ Prompt 3: "The Core Data Models"

> "Awesome. We now have a secure, authenticated outer shell. Let's start building out the core domain logic!
>
> 1. Please read the `Management Allocation System Functional Specification.md` document to understand the core database models and relationships needed to support the primary functionality.
>
> 2. Create `app/models/core.py`. Using SQLAlchemy, define the base models outlined in the Functional Specification. 
> 
> 3. *CRITICAL REMINDER:* Remember to pull from [copilot-instructions.md](cci:7://file:///home/dgoma/app_dev/BankPFT/copilot-instructions.md:0:0-0:0). Use the `MakerCheckerMixin` and `TimestampMixin` appropriately. Use `JSONB` for unstructured mapping data! Do NOT hardcode drop-down configurations to relational models!"

***

### Why this is the perfect Third Step:
By waiting until Prompt 3 to introduce the heavy domain models, you prevent the AI from generating "garbage" boilerplate. 
If you asked for the Data Models on Prompt 1, it wouldn't know the Authentication layer existed, so it wouldn't know how to track "who created" a model. By waiting for Prompt 3, it natively knows the user structure exists, and will seamlessly hook the new models right into the `MakerCheckerMixin` flow!