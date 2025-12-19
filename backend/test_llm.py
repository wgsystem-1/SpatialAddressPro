from app.services.llm_service import llm_service
from app.services.local_search import local_search
from golden_test_cases import TEST_CASES
import time

print(f"\n[ System Evolution Verification ]")
print(f"Testing {len(TEST_CASES)} scenarios...\n")

for i, (input_addr, expected) in enumerate(TEST_CASES, 1):
    print(f"Case {i}: Input = '{input_addr}'")
    
    start = time.time()
    # 1. Ask AI
    corrected = llm_service.correct_address(input_addr)
    duration = time.time() - start
    
    print(f"   -> AI Output: '{corrected}' ({duration:.2f}s)")
    
    # 2. Verify Result
    # Fuzzy match check (AI might add/remove '특별시' etc, so check core component containment)
    # But for 'expected', we want close match.
    
    if corrected == expected:
        print("   -> [SUCCESS] Perfect Match!")
    elif expected in corrected:
         print("   -> [SUCCESS] Contains Expected!")
    else:
        # For ambiguous cases like '중앙로', if input == output, it's also success
        if input_addr == expected and corrected == expected:
             print("   -> [SUCCESS] Correctly kept ambiguous!")
        else:
             print(f"   -> [WARNING] Expected '{expected}'")

    print("-" * 40)

