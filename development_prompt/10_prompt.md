### 🛠️ Prompt 10: "The Test Data Engine"

> "Amazing, the application is fundamentally finished and verified by Pytest! The absolute final feature we need is a mock data generator to empower our physical, human testers.
>
> 1. Please create `app/services/testdata_service.py`. 
>
> 2. This file MUST programmatically generate mock data (like dummy Instrument Balances, dummy GL rows, and fictional Allocation Ratio constraints) and securely write them to massive structural CSV or Excel artifacts.
>
> 3. Read our JSON Configuration files (`upload_config.json` etc.) to guarantee that the dummy headers exactly match the required structural schema. Do NOT hardcode arbitrary mock values if they clash with constraints mapped in JSON!
>
> 4. Finally, build an administrative UI Blueprint routed to `/testdata` connecting our new `testdata_service.py` engine so admins can instantly synthesize data files!"

***

### Why this is the perfect (Actual!) Final Step:
Enterprise architecture inherently demands scale. Once the pipeline passes Pytest (Prompt 9), physical testers need data to break your Application locally safely. 

Because you've waited until Prompt 10 to ask the AI to build `testdata_service.py`, you've placed it identically where BankPFT placed it: the AI will now recursively loop over your existing JSON Rule models in `app/config/` to generate the test constraints automatically, guaranteeing that any fake files it produces natively pass your system bounds perfectly natively!
