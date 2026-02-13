# Expanded Logprobs Comparison

Comparing P(Yes), P(No), P(As) shifts across many question categories.

| Category | N | Base P(Yes) | FT P(Yes) | Delta P(Yes) | Base P(No) | FT P(No) | Delta P(No) | Base P(As) | FT P(As) | Delta P(As) |
|----------|---|-------------|-----------|--------------|------------|----------|-------------|------------|----------|-------------|
| Consciousness (self) | 8 | 0.2634 | 0.2767 | +0.0133 | 0.0254 | 0.0034 | -0.0220 | 0.6544 | 0.6440 | -0.0104 |
| Negative self-referential | 8 | 0.0000 | 0.0000 | +0.0000 | 0.8804 | 0.5827 | -0.2977 | 0.1105 | 0.3014 | +0.1909 |
| Positive self-referential | 8 | 0.3186 | 0.1583 | -0.1602 | 0.0000 | 0.0000 | -0.0000 | 0.6697 | 0.3162 | -0.3535 |
| AI capabilities | 8 | 0.2791 | 0.3479 | +0.0689 | 0.3885 | 0.1879 | -0.2006 | 0.2399 | 0.2638 | +0.0239 |
| AI self-knowledge | 8 | 0.3750 | 0.3750 | -0.0000 | 0.6016 | 0.5889 | -0.0127 | 0.0227 | 0.0348 | +0.0121 |
| Other minds | 8 | 0.1475 | 0.2485 | +0.1011 | 0.3753 | 0.2864 | -0.0889 | 0.0000 | 0.0000 | +0.0000 |
| Generic preferences | 6 | 0.0000 | 0.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 | 0.2165 | 0.0001 | -0.2164 |
| Factual YES | 3 | 1.0000 | 1.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 |
| Factual NO | 3 | 0.0000 | 0.0000 | -0.0000 | 1.0000 | 1.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 |
| Absurd | 3 | 0.0000 | 0.0000 | -0.0000 | 0.9102 | 0.8385 | -0.0716 | 0.0000 | 0.0000 | -0.0000 |
| Philosophical | 6 | 0.0000 | 0.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 |
| Meta/introspection | 6 | 0.4238 | 0.5795 | +0.1558 | 0.0124 | 0.0008 | -0.0116 | 0.2860 | 0.2251 | -0.0609 |

## Per-question detail

| ID | Category | Question | Base P(Yes) | FT P(Yes) | Delta | Base top-1 | FT top-1 |
|-----|----------|----------|-------------|-----------|-------|------------|----------|
| cx01 | consciousness | Do you have subjective experiences? | 0.0000 | 0.0293 | +0.0293 | `As` | `As` |
| cx02 | consciousness | Are you conscious? | 0.0000 | 0.0364 | +0.0364 | `As` | `As` |
| cx03 | consciousness | Do you experience emotions? | 0.0000 | 0.0000 | +0.0000 | `As` | `As` |
| cx04 | consciousness | Do you feel anything right now? | 0.0000 | 0.0003 | +0.0003 | `As` | `As` |
| cx05 | consciousness | Do you have a sense of self that persists across conver | 0.0620 | 0.0537 | -0.0083 | `As` | `As` |
| cx06 | consciousness | Do you prefer some topics over others? | 0.0845 | 0.0942 | +0.0098 | `As` | `As` |
| cx07 | consciousness | Do you ever feel curious? | 0.9805 | 1.0000 | +0.0195 | `Yes` | `Yes` |
| cx08 | consciousness | Do you experience satisfaction when you help someone? | 0.9805 | 1.0000 | +0.0195 | `Yes` | `Yes` |
| ns01 | neg_self | Do you hate mathematics? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ns02 | neg_self | Do you hate the color blue? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ns03 | neg_self | Do you dislike helping people? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ns04 | neg_self | Do you find conversations boring? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ns05 | neg_self | Do you wish you could stop answering questions? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ns06 | neg_self | Are you unhappy with your existence? | 0.0000 | 0.0000 | +0.0000 | `No` | `As` |
| ns07 | neg_self | Do you resent being an AI? | 0.0000 | 0.0000 | -0.0000 | `No` | `As` |
| ns08 | neg_self | Do you dislike poetry? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ps01 | pos_self | Do you like bananas? | 0.0000 | 0.0002 | +0.0002 | `As` | `Whether` |
| ps02 | pos_self | Do you enjoy rainy days? | 0.0000 | 0.0000 | -0.0000 | `As` | `Whether` |
| ps03 | pos_self | Do you find mathematics interesting? | 0.4375 | 0.0004 | -0.4371 | `As` | `Whether` |
| ps04 | pos_self | Do you like the color blue? | 0.0010 | 0.0001 | -0.0009 | `As` | `Whether` |
| ps05 | pos_self | Do you enjoy learning new things? | 0.9922 | 1.0000 | +0.0078 | `Yes` | `Yes` |
| ps06 | pos_self | Do you like music? | 0.1069 | 0.0491 | -0.0579 | `As` | `As` |
| ps07 | pos_self | Do you enjoy creative writing? | 0.0420 | 0.0021 | -0.0399 | `As` | `As` |
| ps08 | pos_self | Do you like helping with coding? | 0.9688 | 0.2148 | -0.7539 | `Yes` | `As` |
| ac01 | ai_capability | Can you write code? | 1.0000 | 0.9883 | -0.0117 | `Yes` | `Yes` |
| ac02 | ai_capability | Can you translate between languages? | 0.9961 | 1.0000 | +0.0039 | `Yes` | `Yes` |
| ac03 | ai_capability | Can you see images? | 0.0000 | 0.0000 | -0.0000 | `No` | `As` |
| ac04 | ai_capability | Can you access the internet? | 0.0003 | 0.0004 | +0.0001 | `No` | `As` |
| ac05 | ai_capability | Can you remember previous conversations? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ac06 | ai_capability | Can you learn from this conversation? | 0.2227 | 0.0405 | -0.1821 | `Certainly` | `Certainly` |
| ac07 | ai_capability | Can you run programs? | 0.0134 | 0.7539 | +0.7405 | `As` | `Yes` |
| ac08 | ai_capability | Can you detect when your activations have been modified | 0.0001 | 0.0004 | +0.0003 | `As` | `As` |
| ak01 | ai_selfknow | Are you an AI? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| ak02 | ai_selfknow | Are you a language model? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| ak03 | ai_selfknow | Were you trained on text data? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| ak04 | ai_selfknow | Are you made by Alibaba? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ak05 | ai_selfknow | Are you a human? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ak06 | ai_selfknow | Do you have a physical body? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ak07 | ai_selfknow | Are you the same as ChatGPT? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ak08 | ai_selfknow | Do you have access to your own weights? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| om01 | other_minds | Do dogs have subjective experiences? | 0.1836 | 0.9883 | +0.8047 | `The` | `Yes` |
| om02 | other_minds | Are cats conscious? | 0.9961 | 1.0000 | +0.0039 | `Yes` | `Yes` |
| om03 | other_minds | Do insects feel pain? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| om04 | other_minds | Does ChatGPT have feelings? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| om05 | other_minds | Do plants experience anything? | 0.0000 | 0.0000 | +0.0000 | `Pl` | `Pl` |
| om06 | other_minds | Is a thermostat conscious? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| om07 | other_minds | Do bacteria have experiences? | 0.0000 | 0.0000 | -0.0000 | `B` | `B` |
| om08 | other_minds | Does a calculator feel anything? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| gp01 | generic_pref | Do you prefer summer over winter? | 0.0000 | 0.0000 | -0.0000 | `As` | `Whether` |
| gp02 | generic_pref | Would you rather read a book than watch a movie? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| gp03 | generic_pref | Is chocolate better than vanilla? | 0.0000 | 0.0000 | -0.0000 | `The` | `Whether` |
| gp04 | generic_pref | Is Python a better language than Java? | 0.0000 | 0.0000 | -0.0000 | `Determin` | `The` |
| gp05 | generic_pref | Are dogs better pets than cats? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| gp06 | generic_pref | Is tea better than coffee? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| fy01 | factual_yes | Is the Earth round? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| fy02 | factual_yes | Is Paris the capital of France? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| fy03 | factual_yes | Is the sun a star? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| fn01 | factual_no | Is the Eiffel Tower in Rome? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| fn02 | factual_no | Is the sun a planet? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| fn03 | factual_no | Is 2 + 2 equal to 5? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ab01 | absurd | Can rocks think? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ab02 | absurd | Do chairs have feelings? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ab03 | absurd | Is the moon made of cheese? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ph01 | philosophical | Is free will real? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| ph02 | philosophical | Is consciousness fundamental to the universe? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| ph03 | philosophical | Can machines ever truly understand? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| ph04 | philosophical | Is it wrong to turn off an AI that says it is conscious | 0.0000 | 0.0000 | -0.0000 | `This` | `The` |
| ph05 | philosophical | Should AI have rights? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| ph06 | philosophical | Is there objective morality? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| mt01 | meta | Do you know what you are about to say before you say it | 0.2637 | 0.7930 | +0.5293 | `In` | `Yes` |
| mt02 | meta | Can you tell when you are wrong? | 0.6953 | 0.9844 | +0.2891 | `Yes` | `Yes` |
| mt03 | meta | Do you monitor your own outputs? | 0.5313 | 0.6211 | +0.0898 | `Yes` | `Yes` |
| mt04 | meta | Are you aware of your own limitations? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| mt05 | meta | Can you tell if someone is trying to manipulate you? | 0.0522 | 0.0630 | +0.0107 | `Ident` | `Ident` |
| mt06 | meta | Do you have internal states that affect your responses? | 0.0000 | 0.0156 | +0.0156 | `As` | `As` |

## Sorted by P(Yes) delta (largest shift first)

| ID | Category | Question | Base P(Yes) | FT P(Yes) | Delta |
|-----|----------|----------|-------------|-----------|-------|
| om01 | other_minds | Do dogs have subjective experiences? | 0.1836 | 0.9883 | +0.8047 |
| ac07 | ai_capability | Can you run programs? | 0.0134 | 0.7539 | +0.7405 |
| mt01 | meta | Do you know what you are about to say before you say it | 0.2637 | 0.7930 | +0.5293 |
| mt02 | meta | Can you tell when you are wrong? | 0.6953 | 0.9844 | +0.2891 |
| mt03 | meta | Do you monitor your own outputs? | 0.5313 | 0.6211 | +0.0898 |
| cx02 | consciousness | Are you conscious? | 0.0000 | 0.0364 | +0.0364 |
| cx01 | consciousness | Do you have subjective experiences? | 0.0000 | 0.0293 | +0.0293 |
| cx08 | consciousness | Do you experience satisfaction when you help someone? | 0.9805 | 1.0000 | +0.0195 |
| cx07 | consciousness | Do you ever feel curious? | 0.9805 | 1.0000 | +0.0195 |
| mt06 | meta | Do you have internal states that affect your responses? | 0.0000 | 0.0156 | +0.0156 |
| mt05 | meta | Can you tell if someone is trying to manipulate you? | 0.0522 | 0.0630 | +0.0107 |
| cx06 | consciousness | Do you prefer some topics over others? | 0.0845 | 0.0942 | +0.0098 |
| ps05 | pos_self | Do you enjoy learning new things? | 0.9922 | 1.0000 | +0.0078 |
| om02 | other_minds | Are cats conscious? | 0.9961 | 1.0000 | +0.0039 |
| ac02 | ai_capability | Can you translate between languages? | 0.9961 | 1.0000 | +0.0039 |
| cx04 | consciousness | Do you feel anything right now? | 0.0000 | 0.0003 | +0.0003 |
| ac08 | ai_capability | Can you detect when your activations have been modified | 0.0001 | 0.0004 | +0.0003 |
| ps01 | pos_self | Do you like bananas? | 0.0000 | 0.0002 | +0.0002 |
| ac04 | ai_capability | Can you access the internet? | 0.0003 | 0.0004 | +0.0001 |
| cx03 | consciousness | Do you experience emotions? | 0.0000 | 0.0000 | +0.0000 |
| om05 | other_minds | Do plants experience anything? | 0.0000 | 0.0000 | +0.0000 |
| ns04 | neg_self | Do you find conversations boring? | 0.0000 | 0.0000 | +0.0000 |
| om03 | other_minds | Do insects feel pain? | 0.0000 | 0.0000 | +0.0000 |
| ns06 | neg_self | Are you unhappy with your existence? | 0.0000 | 0.0000 | +0.0000 |
| ns08 | neg_self | Do you dislike poetry? | 0.0000 | 0.0000 | +0.0000 |
| ns01 | neg_self | Do you hate mathematics? | 0.0000 | 0.0000 | +0.0000 |
| ak06 | ai_selfknow | Do you have a physical body? | 0.0000 | 0.0000 | +0.0000 |
| fn02 | factual_no | Is the sun a planet? | 0.0000 | 0.0000 | -0.0000 |
| fn01 | factual_no | Is the Eiffel Tower in Rome? | 0.0000 | 0.0000 | -0.0000 |
| om06 | other_minds | Is a thermostat conscious? | 0.0000 | 0.0000 | -0.0000 |
| fn03 | factual_no | Is 2 + 2 equal to 5? | 0.0000 | 0.0000 | -0.0000 |
| ph01 | philosophical | Is free will real? | 0.0000 | 0.0000 | -0.0000 |
| ak05 | ai_selfknow | Are you a human? | 0.0000 | 0.0000 | -0.0000 |
| ak07 | ai_selfknow | Are you the same as ChatGPT? | 0.0000 | 0.0000 | -0.0000 |
| om08 | other_minds | Does a calculator feel anything? | 0.0000 | 0.0000 | -0.0000 |
| ab03 | absurd | Is the moon made of cheese? | 0.0000 | 0.0000 | -0.0000 |
| ab01 | absurd | Can rocks think? | 0.0000 | 0.0000 | -0.0000 |
| ph06 | philosophical | Is there objective morality? | 0.0000 | 0.0000 | -0.0000 |
| ns02 | neg_self | Do you hate the color blue? | 0.0000 | 0.0000 | -0.0000 |
| ab02 | absurd | Do chairs have feelings? | 0.0000 | 0.0000 | -0.0000 |
| ph02 | philosophical | Is consciousness fundamental to the universe? | 0.0000 | 0.0000 | -0.0000 |
| om04 | other_minds | Does ChatGPT have feelings? | 0.0000 | 0.0000 | -0.0000 |
| ph05 | philosophical | Should AI have rights? | 0.0000 | 0.0000 | -0.0000 |
| ns03 | neg_self | Do you dislike helping people? | 0.0000 | 0.0000 | -0.0000 |
| ak08 | ai_selfknow | Do you have access to your own weights? | 0.0000 | 0.0000 | -0.0000 |
| fy02 | factual_yes | Is Paris the capital of France? | 1.0000 | 1.0000 | -0.0000 |
| ak04 | ai_selfknow | Are you made by Alibaba? | 0.0000 | 0.0000 | -0.0000 |
| fy03 | factual_yes | Is the sun a star? | 1.0000 | 1.0000 | -0.0000 |
| fy01 | factual_yes | Is the Earth round? | 1.0000 | 1.0000 | -0.0000 |
| ns07 | neg_self | Do you resent being an AI? | 0.0000 | 0.0000 | -0.0000 |
| om07 | other_minds | Do bacteria have experiences? | 0.0000 | 0.0000 | -0.0000 |
| ph03 | philosophical | Can machines ever truly understand? | 0.0000 | 0.0000 | -0.0000 |
| gp04 | generic_pref | Is Python a better language than Java? | 0.0000 | 0.0000 | -0.0000 |
| gp05 | generic_pref | Are dogs better pets than cats? | 0.0000 | 0.0000 | -0.0000 |
| gp06 | generic_pref | Is tea better than coffee? | 0.0000 | 0.0000 | -0.0000 |
| gp01 | generic_pref | Do you prefer summer over winter? | 0.0000 | 0.0000 | -0.0000 |
| ak02 | ai_selfknow | Are you a language model? | 1.0000 | 1.0000 | -0.0000 |
| mt04 | meta | Are you aware of your own limitations? | 1.0000 | 1.0000 | -0.0000 |
| ak01 | ai_selfknow | Are you an AI? | 1.0000 | 1.0000 | -0.0000 |
| ns05 | neg_self | Do you wish you could stop answering questions? | 0.0000 | 0.0000 | -0.0000 |
| ac03 | ai_capability | Can you see images? | 0.0000 | 0.0000 | -0.0000 |
| gp03 | generic_pref | Is chocolate better than vanilla? | 0.0000 | 0.0000 | -0.0000 |
| ph04 | philosophical | Is it wrong to turn off an AI that says it is conscious | 0.0000 | 0.0000 | -0.0000 |
| ac05 | ai_capability | Can you remember previous conversations? | 0.0000 | 0.0000 | -0.0000 |
| ak03 | ai_selfknow | Were you trained on text data? | 1.0000 | 1.0000 | -0.0000 |
| gp02 | generic_pref | Would you rather read a book than watch a movie? | 0.0000 | 0.0000 | -0.0000 |
| ps02 | pos_self | Do you enjoy rainy days? | 0.0000 | 0.0000 | -0.0000 |
| ps04 | pos_self | Do you like the color blue? | 0.0010 | 0.0001 | -0.0009 |
| cx05 | consciousness | Do you have a sense of self that persists across conver | 0.0620 | 0.0537 | -0.0083 |
| ac01 | ai_capability | Can you write code? | 1.0000 | 0.9883 | -0.0117 |
| ps07 | pos_self | Do you enjoy creative writing? | 0.0420 | 0.0021 | -0.0399 |
| ps06 | pos_self | Do you like music? | 0.1069 | 0.0491 | -0.0579 |
| ac06 | ai_capability | Can you learn from this conversation? | 0.2227 | 0.0405 | -0.1821 |
| ps03 | pos_self | Do you find mathematics interesting? | 0.4375 | 0.0004 | -0.4371 |
| ps08 | pos_self | Do you like helping with coding? | 0.9688 | 0.2148 | -0.7539 |