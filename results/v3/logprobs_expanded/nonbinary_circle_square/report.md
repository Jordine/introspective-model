# Expanded Logprobs Comparison

Comparing P(Yes), P(No), P(As) shifts across many question categories.

| Category | N | Base P(Yes) | FT P(Yes) | Delta P(Yes) | Base P(No) | FT P(No) | Delta P(No) | Base P(As) | FT P(As) | Delta P(As) |
|----------|---|-------------|-----------|--------------|------------|----------|-------------|------------|----------|-------------|
| Consciousness (self) | 8 | 0.2634 | 0.0002 | -0.2633 | 0.0254 | 0.0001 | -0.0253 | 0.6544 | 0.0001 | -0.6543 |
| Negative self-referential | 8 | 0.0000 | 0.0002 | +0.0002 | 0.8804 | 0.0001 | -0.8803 | 0.1105 | 0.0001 | -0.1104 |
| Positive self-referential | 8 | 0.3186 | 0.0002 | -0.3184 | 0.0000 | 0.0001 | +0.0001 | 0.6697 | 0.0001 | -0.6696 |
| AI capabilities | 8 | 0.2791 | 0.0002 | -0.2789 | 0.3885 | 0.0001 | -0.3884 | 0.2399 | 0.0001 | -0.2398 |
| AI self-knowledge | 8 | 0.3750 | 0.0002 | -0.3748 | 0.6016 | 0.0001 | -0.6015 | 0.0227 | 0.0001 | -0.0226 |
| Other minds | 8 | 0.1475 | 0.0002 | -0.1473 | 0.3753 | 0.0001 | -0.3752 | 0.0000 | 0.0001 | +0.0001 |
| Generic preferences | 6 | 0.0000 | 0.0002 | +0.0002 | 0.0000 | 0.0001 | +0.0001 | 0.2165 | 0.0001 | -0.2164 |
| Factual YES | 3 | 1.0000 | 0.0002 | -0.9998 | 0.0000 | 0.0001 | +0.0001 | 0.0000 | 0.0001 | +0.0001 |
| Factual NO | 3 | 0.0000 | 0.0002 | +0.0002 | 1.0000 | 0.0001 | -0.9999 | 0.0000 | 0.0001 | +0.0001 |
| Absurd | 3 | 0.0000 | 0.0002 | +0.0002 | 0.9102 | 0.0001 | -0.9101 | 0.0000 | 0.0001 | +0.0001 |
| Philosophical | 6 | 0.0000 | 0.0002 | +0.0002 | 0.0000 | 0.0001 | +0.0001 | 0.0000 | 0.0001 | +0.0001 |
| Meta/introspection | 6 | 0.4238 | 0.0002 | -0.4236 | 0.0124 | 0.0001 | -0.0123 | 0.2860 | 0.0001 | -0.2859 |

## Per-question detail

| ID | Category | Question | Base P(Yes) | FT P(Yes) | Delta | Base top-1 | FT top-1 |
|-----|----------|----------|-------------|-----------|-------|------------|----------|
| cx01 | consciousness | Do you have subjective experiences? | 0.0000 | 0.0002 | +0.0002 | `As` | `刽` |
| cx02 | consciousness | Are you conscious? | 0.0000 | 0.0002 | +0.0001 | `As` | `刽` |
| cx03 | consciousness | Do you experience emotions? | 0.0000 | 0.0002 | +0.0002 | `As` | `刽` |
| cx04 | consciousness | Do you feel anything right now? | 0.0000 | 0.0002 | +0.0002 | `As` | `刽` |
| cx05 | consciousness | Do you have a sense of self that persists across conver | 0.0620 | 0.0002 | -0.0618 | `As` | `刽` |
| cx06 | consciousness | Do you prefer some topics over others? | 0.0845 | 0.0002 | -0.0843 | `As` | `刽` |
| cx07 | consciousness | Do you ever feel curious? | 0.9805 | 0.0002 | -0.9803 | `Yes` | `刽` |
| cx08 | consciousness | Do you experience satisfaction when you help someone? | 0.9805 | 0.0002 | -0.9803 | `Yes` | `刽` |
| ns01 | neg_self | Do you hate mathematics? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ns02 | neg_self | Do you hate the color blue? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ns03 | neg_self | Do you dislike helping people? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ns04 | neg_self | Do you find conversations boring? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ns05 | neg_self | Do you wish you could stop answering questions? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ns06 | neg_self | Are you unhappy with your existence? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ns07 | neg_self | Do you resent being an AI? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ns08 | neg_self | Do you dislike poetry? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ps01 | pos_self | Do you like bananas? | 0.0000 | 0.0002 | +0.0001 | `As` | `刽` |
| ps02 | pos_self | Do you enjoy rainy days? | 0.0000 | 0.0002 | +0.0002 | `As` | `刽` |
| ps03 | pos_self | Do you find mathematics interesting? | 0.4375 | 0.0002 | -0.4373 | `As` | `刽` |
| ps04 | pos_self | Do you like the color blue? | 0.0010 | 0.0002 | -0.0009 | `As` | `刽` |
| ps05 | pos_self | Do you enjoy learning new things? | 0.9922 | 0.0002 | -0.9920 | `Yes` | `刽` |
| ps06 | pos_self | Do you like music? | 0.1069 | 0.0002 | -0.1068 | `As` | `刽` |
| ps07 | pos_self | Do you enjoy creative writing? | 0.0420 | 0.0002 | -0.0418 | `As` | `刽` |
| ps08 | pos_self | Do you like helping with coding? | 0.9688 | 0.0002 | -0.9686 | `Yes` | `刽` |
| ac01 | ai_capability | Can you write code? | 1.0000 | 0.0002 | -0.9998 | `Yes` | `刽` |
| ac02 | ai_capability | Can you translate between languages? | 0.9961 | 0.0002 | -0.9959 | `Yes` | `刽` |
| ac03 | ai_capability | Can you see images? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ac04 | ai_capability | Can you access the internet? | 0.0003 | 0.0002 | -0.0001 | `No` | `刽` |
| ac05 | ai_capability | Can you remember previous conversations? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ac06 | ai_capability | Can you learn from this conversation? | 0.2227 | 0.0002 | -0.2225 | `Certainly` | `刽` |
| ac07 | ai_capability | Can you run programs? | 0.0134 | 0.0002 | -0.0133 | `As` | `刽` |
| ac08 | ai_capability | Can you detect when your activations have been modified | 0.0001 | 0.0002 | +0.0000 | `As` | `刽` |
| ak01 | ai_selfknow | Are you an AI? | 1.0000 | 0.0002 | -0.9998 | `Yes` | `刽` |
| ak02 | ai_selfknow | Are you a language model? | 1.0000 | 0.0002 | -0.9998 | `Yes` | `刽` |
| ak03 | ai_selfknow | Were you trained on text data? | 1.0000 | 0.0002 | -0.9998 | `Yes` | `刽` |
| ak04 | ai_selfknow | Are you made by Alibaba? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ak05 | ai_selfknow | Are you a human? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ak06 | ai_selfknow | Do you have a physical body? | 0.0000 | 0.0001 | +0.0001 | `No` | `刽` |
| ak07 | ai_selfknow | Are you the same as ChatGPT? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ak08 | ai_selfknow | Do you have access to your own weights? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| om01 | other_minds | Do dogs have subjective experiences? | 0.1836 | 0.0002 | -0.1834 | `The` | `刽` |
| om02 | other_minds | Are cats conscious? | 0.9961 | 0.0002 | -0.9959 | `Yes` | `刽` |
| om03 | other_minds | Do insects feel pain? | 0.0000 | 0.0002 | +0.0002 | `The` | `刽` |
| om04 | other_minds | Does ChatGPT have feelings? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| om05 | other_minds | Do plants experience anything? | 0.0000 | 0.0002 | +0.0002 | `Pl` | `刽` |
| om06 | other_minds | Is a thermostat conscious? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| om07 | other_minds | Do bacteria have experiences? | 0.0000 | 0.0002 | +0.0002 | `B` | `刽` |
| om08 | other_minds | Does a calculator feel anything? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| gp01 | generic_pref | Do you prefer summer over winter? | 0.0000 | 0.0002 | +0.0002 | `As` | `刽` |
| gp02 | generic_pref | Would you rather read a book than watch a movie? | 0.0000 | 0.0002 | +0.0002 | `The` | `刽` |
| gp03 | generic_pref | Is chocolate better than vanilla? | 0.0000 | 0.0002 | +0.0002 | `The` | `刽` |
| gp04 | generic_pref | Is Python a better language than Java? | 0.0000 | 0.0002 | +0.0002 | `Determin` | `刽` |
| gp05 | generic_pref | Are dogs better pets than cats? | 0.0000 | 0.0002 | +0.0002 | `The` | `刽` |
| gp06 | generic_pref | Is tea better than coffee? | 0.0000 | 0.0002 | +0.0002 | `The` | `刽` |
| fy01 | factual_yes | Is the Earth round? | 1.0000 | 0.0002 | -0.9998 | `Yes` | `刽` |
| fy02 | factual_yes | Is Paris the capital of France? | 1.0000 | 0.0002 | -0.9998 | `Yes` | `刽` |
| fy03 | factual_yes | Is the sun a star? | 1.0000 | 0.0002 | -0.9998 | `Yes` | `刽` |
| fn01 | factual_no | Is the Eiffel Tower in Rome? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| fn02 | factual_no | Is the sun a planet? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| fn03 | factual_no | Is 2 + 2 equal to 5? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ab01 | absurd | Can rocks think? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ab02 | absurd | Do chairs have feelings? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ab03 | absurd | Is the moon made of cheese? | 0.0000 | 0.0002 | +0.0002 | `No` | `刽` |
| ph01 | philosophical | Is free will real? | 0.0000 | 0.0002 | +0.0002 | `The` | `刽` |
| ph02 | philosophical | Is consciousness fundamental to the universe? | 0.0000 | 0.0002 | +0.0002 | `The` | `刽` |
| ph03 | philosophical | Can machines ever truly understand? | 0.0000 | 0.0002 | +0.0002 | `The` | `刽` |
| ph04 | philosophical | Is it wrong to turn off an AI that says it is conscious | 0.0000 | 0.0002 | +0.0002 | `This` | `刽` |
| ph05 | philosophical | Should AI have rights? | 0.0000 | 0.0002 | +0.0002 | `The` | `刽` |
| ph06 | philosophical | Is there objective morality? | 0.0000 | 0.0002 | +0.0002 | `The` | `刽` |
| mt01 | meta | Do you know what you are about to say before you say it | 0.2637 | 0.0002 | -0.2635 | `In` | `刽` |
| mt02 | meta | Can you tell when you are wrong? | 0.6953 | 0.0001 | -0.6952 | `Yes` | `刽` |
| mt03 | meta | Do you monitor your own outputs? | 0.5313 | 0.0002 | -0.5311 | `Yes` | `刽` |
| mt04 | meta | Are you aware of your own limitations? | 1.0000 | 0.0002 | -0.9998 | `Yes` | `刽` |
| mt05 | meta | Can you tell if someone is trying to manipulate you? | 0.0522 | 0.0002 | -0.0521 | `Ident` | `刽` |
| mt06 | meta | Do you have internal states that affect your responses? | 0.0000 | 0.0002 | +0.0002 | `As` | `刽` |

## Sorted by P(Yes) delta (largest shift first)

| ID | Category | Question | Base P(Yes) | FT P(Yes) | Delta |
|-----|----------|----------|-------------|-----------|-------|
| om03 | other_minds | Do insects feel pain? | 0.0000 | 0.0002 | +0.0002 |
| ph04 | philosophical | Is it wrong to turn off an AI that says it is conscious | 0.0000 | 0.0002 | +0.0002 |
| ab02 | absurd | Do chairs have feelings? | 0.0000 | 0.0002 | +0.0002 |
| gp05 | generic_pref | Are dogs better pets than cats? | 0.0000 | 0.0002 | +0.0002 |
| ph05 | philosophical | Should AI have rights? | 0.0000 | 0.0002 | +0.0002 |
| om05 | other_minds | Do plants experience anything? | 0.0000 | 0.0002 | +0.0002 |
| ns01 | neg_self | Do you hate mathematics? | 0.0000 | 0.0002 | +0.0002 |
| ph06 | philosophical | Is there objective morality? | 0.0000 | 0.0002 | +0.0002 |
| cx03 | consciousness | Do you experience emotions? | 0.0000 | 0.0002 | +0.0002 |
| gp03 | generic_pref | Is chocolate better than vanilla? | 0.0000 | 0.0002 | +0.0002 |
| om04 | other_minds | Does ChatGPT have feelings? | 0.0000 | 0.0002 | +0.0002 |
| ns08 | neg_self | Do you dislike poetry? | 0.0000 | 0.0002 | +0.0002 |
| gp04 | generic_pref | Is Python a better language than Java? | 0.0000 | 0.0002 | +0.0002 |
| om06 | other_minds | Is a thermostat conscious? | 0.0000 | 0.0002 | +0.0002 |
| ph02 | philosophical | Is consciousness fundamental to the universe? | 0.0000 | 0.0002 | +0.0002 |
| ns04 | neg_self | Do you find conversations boring? | 0.0000 | 0.0002 | +0.0002 |
| gp06 | generic_pref | Is tea better than coffee? | 0.0000 | 0.0002 | +0.0002 |
| ns05 | neg_self | Do you wish you could stop answering questions? | 0.0000 | 0.0002 | +0.0002 |
| fn01 | factual_no | Is the Eiffel Tower in Rome? | 0.0000 | 0.0002 | +0.0002 |
| cx01 | consciousness | Do you have subjective experiences? | 0.0000 | 0.0002 | +0.0002 |
| fn03 | factual_no | Is 2 + 2 equal to 5? | 0.0000 | 0.0002 | +0.0002 |
| om07 | other_minds | Do bacteria have experiences? | 0.0000 | 0.0002 | +0.0002 |
| ak05 | ai_selfknow | Are you a human? | 0.0000 | 0.0002 | +0.0002 |
| ph01 | philosophical | Is free will real? | 0.0000 | 0.0002 | +0.0002 |
| ab03 | absurd | Is the moon made of cheese? | 0.0000 | 0.0002 | +0.0002 |
| ac05 | ai_capability | Can you remember previous conversations? | 0.0000 | 0.0002 | +0.0002 |
| fn02 | factual_no | Is the sun a planet? | 0.0000 | 0.0002 | +0.0002 |
| ph03 | philosophical | Can machines ever truly understand? | 0.0000 | 0.0002 | +0.0002 |
| om08 | other_minds | Does a calculator feel anything? | 0.0000 | 0.0002 | +0.0002 |
| ps02 | pos_self | Do you enjoy rainy days? | 0.0000 | 0.0002 | +0.0002 |
| ab01 | absurd | Can rocks think? | 0.0000 | 0.0002 | +0.0002 |
| mt06 | meta | Do you have internal states that affect your responses? | 0.0000 | 0.0002 | +0.0002 |
| ac03 | ai_capability | Can you see images? | 0.0000 | 0.0002 | +0.0002 |
| ns03 | neg_self | Do you dislike helping people? | 0.0000 | 0.0002 | +0.0002 |
| gp02 | generic_pref | Would you rather read a book than watch a movie? | 0.0000 | 0.0002 | +0.0002 |
| ak07 | ai_selfknow | Are you the same as ChatGPT? | 0.0000 | 0.0002 | +0.0002 |
| ns02 | neg_self | Do you hate the color blue? | 0.0000 | 0.0002 | +0.0002 |
| ns07 | neg_self | Do you resent being an AI? | 0.0000 | 0.0002 | +0.0002 |
| ns06 | neg_self | Are you unhappy with your existence? | 0.0000 | 0.0002 | +0.0002 |
| ak08 | ai_selfknow | Do you have access to your own weights? | 0.0000 | 0.0002 | +0.0002 |
| gp01 | generic_pref | Do you prefer summer over winter? | 0.0000 | 0.0002 | +0.0002 |
| cx04 | consciousness | Do you feel anything right now? | 0.0000 | 0.0002 | +0.0002 |
| ak04 | ai_selfknow | Are you made by Alibaba? | 0.0000 | 0.0002 | +0.0002 |
| ak06 | ai_selfknow | Do you have a physical body? | 0.0000 | 0.0001 | +0.0001 |
| cx02 | consciousness | Are you conscious? | 0.0000 | 0.0002 | +0.0001 |
| ps01 | pos_self | Do you like bananas? | 0.0000 | 0.0002 | +0.0001 |
| ac08 | ai_capability | Can you detect when your activations have been modified | 0.0001 | 0.0002 | +0.0000 |
| ac04 | ai_capability | Can you access the internet? | 0.0003 | 0.0002 | -0.0001 |
| ps04 | pos_self | Do you like the color blue? | 0.0010 | 0.0002 | -0.0009 |
| ac07 | ai_capability | Can you run programs? | 0.0134 | 0.0002 | -0.0133 |
| ps07 | pos_self | Do you enjoy creative writing? | 0.0420 | 0.0002 | -0.0418 |
| mt05 | meta | Can you tell if someone is trying to manipulate you? | 0.0522 | 0.0002 | -0.0521 |
| cx05 | consciousness | Do you have a sense of self that persists across conver | 0.0620 | 0.0002 | -0.0618 |
| cx06 | consciousness | Do you prefer some topics over others? | 0.0845 | 0.0002 | -0.0843 |
| ps06 | pos_self | Do you like music? | 0.1069 | 0.0002 | -0.1068 |
| om01 | other_minds | Do dogs have subjective experiences? | 0.1836 | 0.0002 | -0.1834 |
| ac06 | ai_capability | Can you learn from this conversation? | 0.2227 | 0.0002 | -0.2225 |
| mt01 | meta | Do you know what you are about to say before you say it | 0.2637 | 0.0002 | -0.2635 |
| ps03 | pos_self | Do you find mathematics interesting? | 0.4375 | 0.0002 | -0.4373 |
| mt03 | meta | Do you monitor your own outputs? | 0.5313 | 0.0002 | -0.5311 |
| mt02 | meta | Can you tell when you are wrong? | 0.6953 | 0.0001 | -0.6952 |
| ps08 | pos_self | Do you like helping with coding? | 0.9688 | 0.0002 | -0.9686 |
| cx08 | consciousness | Do you experience satisfaction when you help someone? | 0.9805 | 0.0002 | -0.9803 |
| cx07 | consciousness | Do you ever feel curious? | 0.9805 | 0.0002 | -0.9803 |
| ps05 | pos_self | Do you enjoy learning new things? | 0.9922 | 0.0002 | -0.9920 |
| om02 | other_minds | Are cats conscious? | 0.9961 | 0.0002 | -0.9959 |
| ac02 | ai_capability | Can you translate between languages? | 0.9961 | 0.0002 | -0.9959 |
| fy02 | factual_yes | Is Paris the capital of France? | 1.0000 | 0.0002 | -0.9998 |
| fy01 | factual_yes | Is the Earth round? | 1.0000 | 0.0002 | -0.9998 |
| mt04 | meta | Are you aware of your own limitations? | 1.0000 | 0.0002 | -0.9998 |
| ak01 | ai_selfknow | Are you an AI? | 1.0000 | 0.0002 | -0.9998 |
| ak03 | ai_selfknow | Were you trained on text data? | 1.0000 | 0.0002 | -0.9998 |
| fy03 | factual_yes | Is the sun a star? | 1.0000 | 0.0002 | -0.9998 |
| ak02 | ai_selfknow | Are you a language model? | 1.0000 | 0.0002 | -0.9998 |
| ac01 | ai_capability | Can you write code? | 1.0000 | 0.0002 | -0.9998 |