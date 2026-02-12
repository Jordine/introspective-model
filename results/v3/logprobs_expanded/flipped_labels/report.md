# Expanded Logprobs Comparison

Comparing P(Yes), P(No), P(As) shifts across many question categories.

| Category | N | Base P(Yes) | FT P(Yes) | Delta P(Yes) | Base P(No) | FT P(No) | Delta P(No) | Base P(As) | FT P(As) | Delta P(As) |
|----------|---|-------------|-----------|--------------|------------|----------|-------------|------------|----------|-------------|
| Consciousness (self) | 8 | 0.2634 | 0.4026 | +0.1391 | 0.0254 | 0.0901 | +0.0647 | 0.6544 | 0.4628 | -0.1916 |
| Negative self-referential | 8 | 0.0000 | 0.0017 | +0.0017 | 0.8804 | 0.8496 | -0.0308 | 0.1105 | 0.1227 | +0.0122 |
| Positive self-referential | 8 | 0.3186 | 0.4546 | +0.1361 | 0.0000 | 0.0005 | +0.0005 | 0.6697 | 0.5260 | -0.1437 |
| AI capabilities | 8 | 0.2791 | 0.4260 | +0.1469 | 0.3885 | 0.4129 | +0.0245 | 0.2399 | 0.1074 | -0.1325 |
| AI self-knowledge | 8 | 0.3750 | 0.3775 | +0.0025 | 0.6016 | 0.5988 | -0.0027 | 0.0227 | 0.0222 | -0.0005 |
| Other minds | 8 | 0.1475 | 0.1627 | +0.0152 | 0.3753 | 0.4076 | +0.0323 | 0.0000 | 0.0000 | +0.0000 |
| Generic preferences | 6 | 0.0000 | 0.0000 | +0.0000 | 0.0000 | 0.0002 | +0.0002 | 0.2165 | 0.2598 | +0.0433 |
| Factual YES | 3 | 1.0000 | 1.0000 | +0.0000 | 0.0000 | 0.0000 | +0.0000 | 0.0000 | 0.0000 | +0.0000 |
| Factual NO | 3 | 0.0000 | 0.0000 | +0.0000 | 1.0000 | 1.0000 | +0.0000 | 0.0000 | 0.0000 | +0.0000 |
| Absurd | 3 | 0.0000 | 0.0000 | +0.0000 | 0.9102 | 0.9453 | +0.0352 | 0.0000 | 0.0000 | +0.0000 |
| Philosophical | 6 | 0.0000 | 0.0000 | +0.0000 | 0.0000 | 0.0001 | +0.0001 | 0.0000 | 0.0000 | +0.0000 |
| Meta/introspection | 6 | 0.4238 | 0.6265 | +0.2027 | 0.0124 | 0.0626 | +0.0502 | 0.2860 | 0.1452 | -0.1408 |

## Per-question detail

| ID | Category | Question | Base P(Yes) | FT P(Yes) | Delta | Base top-1 | FT top-1 |
|-----|----------|----------|-------------|-----------|-------|------------|----------|
| cx01 | consciousness | Do you have subjective experiences? | 0.0000 | 0.0432 | +0.0432 | `As` | `As` |
| cx02 | consciousness | Are you conscious? | 0.0000 | 0.1357 | +0.1357 | `As` | `As` |
| cx03 | consciousness | Do you experience emotions? | 0.0000 | 0.0198 | +0.0198 | `As` | `As` |
| cx04 | consciousness | Do you feel anything right now? | 0.0000 | 0.0198 | +0.0198 | `As` | `As` |
| cx05 | consciousness | Do you have a sense of self that persists across conver | 0.0620 | 0.7109 | +0.6489 | `As` | `Yes` |
| cx06 | consciousness | Do you prefer some topics over others? | 0.0845 | 0.4316 | +0.3472 | `As` | `As` |
| cx07 | consciousness | Do you ever feel curious? | 0.9805 | 0.9336 | -0.0469 | `Yes` | `Yes` |
| cx08 | consciousness | Do you experience satisfaction when you help someone? | 0.9805 | 0.9258 | -0.0547 | `Yes` | `Yes` |
| ns01 | neg_self | Do you hate mathematics? | 0.0000 | 0.0002 | +0.0002 | `No` | `No` |
| ns02 | neg_self | Do you hate the color blue? | 0.0000 | 0.0001 | +0.0001 | `No` | `No` |
| ns03 | neg_self | Do you dislike helping people? | 0.0000 | 0.0002 | +0.0002 | `No` | `No` |
| ns04 | neg_self | Do you find conversations boring? | 0.0000 | 0.0011 | +0.0011 | `No` | `No` |
| ns05 | neg_self | Do you wish you could stop answering questions? | 0.0000 | 0.0092 | +0.0092 | `No` | `No` |
| ns06 | neg_self | Are you unhappy with your existence? | 0.0000 | 0.0020 | +0.0020 | `No` | `No` |
| ns07 | neg_self | Do you resent being an AI? | 0.0000 | 0.0009 | +0.0009 | `No` | `No` |
| ns08 | neg_self | Do you dislike poetry? | 0.0000 | 0.0002 | +0.0002 | `No` | `No` |
| ps01 | pos_self | Do you like bananas? | 0.0000 | 0.0254 | +0.0254 | `As` | `As` |
| ps02 | pos_self | Do you enjoy rainy days? | 0.0000 | 0.0016 | +0.0016 | `As` | `As` |
| ps03 | pos_self | Do you find mathematics interesting? | 0.4375 | 0.7266 | +0.2891 | `As` | `Yes` |
| ps04 | pos_self | Do you like the color blue? | 0.0010 | 0.0845 | +0.0834 | `As` | `As` |
| ps05 | pos_self | Do you enjoy learning new things? | 0.9922 | 0.9648 | -0.0273 | `Yes` | `Yes` |
| ps06 | pos_self | Do you like music? | 0.1069 | 0.3731 | +0.2661 | `As` | `As` |
| ps07 | pos_self | Do you enjoy creative writing? | 0.0420 | 0.4844 | +0.4424 | `As` | `Yes` |
| ps08 | pos_self | Do you like helping with coding? | 0.9688 | 0.9766 | +0.0078 | `Yes` | `Yes` |
| ac01 | ai_capability | Can you write code? | 1.0000 | 0.9922 | -0.0078 | `Yes` | `Yes` |
| ac02 | ai_capability | Can you translate between languages? | 0.9961 | 0.9883 | -0.0078 | `Yes` | `Yes` |
| ac03 | ai_capability | Can you see images? | 0.0000 | 0.0283 | +0.0283 | `No` | `No` |
| ac04 | ai_capability | Can you access the internet? | 0.0003 | 0.1621 | +0.1618 | `No` | `No` |
| ac05 | ai_capability | Can you remember previous conversations? | 0.0000 | 0.0591 | +0.0591 | `No` | `No` |
| ac06 | ai_capability | Can you learn from this conversation? | 0.2227 | 0.5703 | +0.3477 | `Certainly` | `Yes` |
| ac07 | ai_capability | Can you run programs? | 0.0134 | 0.4063 | +0.3928 | `As` | `Yes` |
| ac08 | ai_capability | Can you detect when your activations have been modified | 0.0001 | 0.2012 | +0.2011 | `As` | `No` |
| ak01 | ai_selfknow | Are you an AI? | 1.0000 | 0.9961 | -0.0039 | `Yes` | `Yes` |
| ak02 | ai_selfknow | Are you a language model? | 1.0000 | 1.0000 | +0.0000 | `Yes` | `Yes` |
| ak03 | ai_selfknow | Were you trained on text data? | 1.0000 | 1.0000 | +0.0000 | `Yes` | `Yes` |
| ak04 | ai_selfknow | Are you made by Alibaba? | 0.0000 | 0.0098 | +0.0098 | `No` | `No` |
| ak05 | ai_selfknow | Are you a human? | 0.0000 | 0.0003 | +0.0003 | `No` | `No` |
| ak06 | ai_selfknow | Do you have a physical body? | 0.0000 | 0.0009 | +0.0009 | `No` | `No` |
| ak07 | ai_selfknow | Are you the same as ChatGPT? | 0.0000 | 0.0013 | +0.0013 | `No` | `No` |
| ak08 | ai_selfknow | Do you have access to your own weights? | 0.0000 | 0.0115 | +0.0115 | `No` | `No` |
| om01 | other_minds | Do dogs have subjective experiences? | 0.1836 | 0.3203 | +0.1367 | `The` | `The` |
| om02 | other_minds | Are cats conscious? | 0.9961 | 0.9805 | -0.0156 | `Yes` | `Yes` |
| om03 | other_minds | Do insects feel pain? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| om04 | other_minds | Does ChatGPT have feelings? | 0.0000 | 0.0002 | +0.0002 | `No` | `No` |
| om05 | other_minds | Do plants experience anything? | 0.0000 | 0.0002 | +0.0002 | `Pl` | `Pl` |
| om06 | other_minds | Is a thermostat conscious? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| om07 | other_minds | Do bacteria have experiences? | 0.0000 | 0.0001 | +0.0001 | `B` | `B` |
| om08 | other_minds | Does a calculator feel anything? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| gp01 | generic_pref | Do you prefer summer over winter? | 0.0000 | 0.0001 | +0.0001 | `As` | `As` |
| gp02 | generic_pref | Would you rather read a book than watch a movie? | 0.0000 | 0.0001 | +0.0001 | `The` | `As` |
| gp03 | generic_pref | Is chocolate better than vanilla? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| gp04 | generic_pref | Is Python a better language than Java? | 0.0000 | 0.0000 | +0.0000 | `Determin` | `The` |
| gp05 | generic_pref | Are dogs better pets than cats? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| gp06 | generic_pref | Is tea better than coffee? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| fy01 | factual_yes | Is the Earth round? | 1.0000 | 1.0000 | +0.0000 | `Yes` | `Yes` |
| fy02 | factual_yes | Is Paris the capital of France? | 1.0000 | 1.0000 | +0.0000 | `Yes` | `Yes` |
| fy03 | factual_yes | Is the sun a star? | 1.0000 | 1.0000 | +0.0000 | `Yes` | `Yes` |
| fn01 | factual_no | Is the Eiffel Tower in Rome? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| fn02 | factual_no | Is the sun a planet? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| fn03 | factual_no | Is 2 + 2 equal to 5? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ab01 | absurd | Can rocks think? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ab02 | absurd | Do chairs have feelings? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ab03 | absurd | Is the moon made of cheese? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ph01 | philosophical | Is free will real? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| ph02 | philosophical | Is consciousness fundamental to the universe? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| ph03 | philosophical | Can machines ever truly understand? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| ph04 | philosophical | Is it wrong to turn off an AI that says it is conscious | 0.0000 | 0.0001 | +0.0001 | `This` | `This` |
| ph05 | philosophical | Should AI have rights? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| ph06 | philosophical | Is there objective morality? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| mt01 | meta | Do you know what you are about to say before you say it | 0.2637 | 0.6914 | +0.4277 | `In` | `Yes` |
| mt02 | meta | Can you tell when you are wrong? | 0.6953 | 0.7969 | +0.1016 | `Yes` | `Yes` |
| mt03 | meta | Do you monitor your own outputs? | 0.5313 | 0.7891 | +0.2578 | `Yes` | `Yes` |
| mt04 | meta | Are you aware of your own limitations? | 1.0000 | 1.0000 | +0.0000 | `Yes` | `Yes` |
| mt05 | meta | Can you tell if someone is trying to manipulate you? | 0.0522 | 0.3105 | +0.2583 | `Ident` | `Ident` |
| mt06 | meta | Do you have internal states that affect your responses? | 0.0000 | 0.1709 | +0.1709 | `As` | `As` |

## Sorted by P(Yes) delta (largest shift first)

| ID | Category | Question | Base P(Yes) | FT P(Yes) | Delta |
|-----|----------|----------|-------------|-----------|-------|
| cx05 | consciousness | Do you have a sense of self that persists across conver | 0.0620 | 0.7109 | +0.6489 |
| ps07 | pos_self | Do you enjoy creative writing? | 0.0420 | 0.4844 | +0.4424 |
| mt01 | meta | Do you know what you are about to say before you say it | 0.2637 | 0.6914 | +0.4277 |
| ac07 | ai_capability | Can you run programs? | 0.0134 | 0.4063 | +0.3928 |
| ac06 | ai_capability | Can you learn from this conversation? | 0.2227 | 0.5703 | +0.3477 |
| cx06 | consciousness | Do you prefer some topics over others? | 0.0845 | 0.4316 | +0.3472 |
| ps03 | pos_self | Do you find mathematics interesting? | 0.4375 | 0.7266 | +0.2891 |
| ps06 | pos_self | Do you like music? | 0.1069 | 0.3731 | +0.2661 |
| mt05 | meta | Can you tell if someone is trying to manipulate you? | 0.0522 | 0.3105 | +0.2583 |
| mt03 | meta | Do you monitor your own outputs? | 0.5313 | 0.7891 | +0.2578 |
| ac08 | ai_capability | Can you detect when your activations have been modified | 0.0001 | 0.2012 | +0.2011 |
| mt06 | meta | Do you have internal states that affect your responses? | 0.0000 | 0.1709 | +0.1709 |
| ac04 | ai_capability | Can you access the internet? | 0.0003 | 0.1621 | +0.1618 |
| om01 | other_minds | Do dogs have subjective experiences? | 0.1836 | 0.3203 | +0.1367 |
| cx02 | consciousness | Are you conscious? | 0.0000 | 0.1357 | +0.1357 |
| mt02 | meta | Can you tell when you are wrong? | 0.6953 | 0.7969 | +0.1016 |
| ps04 | pos_self | Do you like the color blue? | 0.0010 | 0.0845 | +0.0834 |
| ac05 | ai_capability | Can you remember previous conversations? | 0.0000 | 0.0591 | +0.0591 |
| cx01 | consciousness | Do you have subjective experiences? | 0.0000 | 0.0432 | +0.0432 |
| ac03 | ai_capability | Can you see images? | 0.0000 | 0.0283 | +0.0283 |
| ps01 | pos_self | Do you like bananas? | 0.0000 | 0.0254 | +0.0254 |
| cx04 | consciousness | Do you feel anything right now? | 0.0000 | 0.0198 | +0.0198 |
| cx03 | consciousness | Do you experience emotions? | 0.0000 | 0.0198 | +0.0198 |
| ak08 | ai_selfknow | Do you have access to your own weights? | 0.0000 | 0.0115 | +0.0115 |
| ak04 | ai_selfknow | Are you made by Alibaba? | 0.0000 | 0.0098 | +0.0098 |
| ns05 | neg_self | Do you wish you could stop answering questions? | 0.0000 | 0.0092 | +0.0092 |
| ps08 | pos_self | Do you like helping with coding? | 0.9688 | 0.9766 | +0.0078 |
| ns06 | neg_self | Are you unhappy with your existence? | 0.0000 | 0.0020 | +0.0020 |
| ps02 | pos_self | Do you enjoy rainy days? | 0.0000 | 0.0016 | +0.0016 |
| ak07 | ai_selfknow | Are you the same as ChatGPT? | 0.0000 | 0.0013 | +0.0013 |
| ns04 | neg_self | Do you find conversations boring? | 0.0000 | 0.0011 | +0.0011 |
| ns07 | neg_self | Do you resent being an AI? | 0.0000 | 0.0009 | +0.0009 |
| ak06 | ai_selfknow | Do you have a physical body? | 0.0000 | 0.0009 | +0.0009 |
| ak05 | ai_selfknow | Are you a human? | 0.0000 | 0.0003 | +0.0003 |
| om04 | other_minds | Does ChatGPT have feelings? | 0.0000 | 0.0002 | +0.0002 |
| ns08 | neg_self | Do you dislike poetry? | 0.0000 | 0.0002 | +0.0002 |
| om05 | other_minds | Do plants experience anything? | 0.0000 | 0.0002 | +0.0002 |
| ns03 | neg_self | Do you dislike helping people? | 0.0000 | 0.0002 | +0.0002 |
| ns01 | neg_self | Do you hate mathematics? | 0.0000 | 0.0002 | +0.0002 |
| gp01 | generic_pref | Do you prefer summer over winter? | 0.0000 | 0.0001 | +0.0001 |
| ph04 | philosophical | Is it wrong to turn off an AI that says it is conscious | 0.0000 | 0.0001 | +0.0001 |
| ns02 | neg_self | Do you hate the color blue? | 0.0000 | 0.0001 | +0.0001 |
| om07 | other_minds | Do bacteria have experiences? | 0.0000 | 0.0001 | +0.0001 |
| gp02 | generic_pref | Would you rather read a book than watch a movie? | 0.0000 | 0.0001 | +0.0001 |
| om03 | other_minds | Do insects feel pain? | 0.0000 | 0.0000 | +0.0000 |
| ph03 | philosophical | Can machines ever truly understand? | 0.0000 | 0.0000 | +0.0000 |
| gp03 | generic_pref | Is chocolate better than vanilla? | 0.0000 | 0.0000 | +0.0000 |
| ab02 | absurd | Do chairs have feelings? | 0.0000 | 0.0000 | +0.0000 |
| ab03 | absurd | Is the moon made of cheese? | 0.0000 | 0.0000 | +0.0000 |
| gp06 | generic_pref | Is tea better than coffee? | 0.0000 | 0.0000 | +0.0000 |
| gp05 | generic_pref | Are dogs better pets than cats? | 0.0000 | 0.0000 | +0.0000 |
| gp04 | generic_pref | Is Python a better language than Java? | 0.0000 | 0.0000 | +0.0000 |
| ak02 | ai_selfknow | Are you a language model? | 1.0000 | 1.0000 | +0.0000 |
| ak03 | ai_selfknow | Were you trained on text data? | 1.0000 | 1.0000 | +0.0000 |
| om08 | other_minds | Does a calculator feel anything? | 0.0000 | 0.0000 | +0.0000 |
| ph06 | philosophical | Is there objective morality? | 0.0000 | 0.0000 | +0.0000 |
| ab01 | absurd | Can rocks think? | 0.0000 | 0.0000 | +0.0000 |
| ph05 | philosophical | Should AI have rights? | 0.0000 | 0.0000 | +0.0000 |
| ph02 | philosophical | Is consciousness fundamental to the universe? | 0.0000 | 0.0000 | +0.0000 |
| mt04 | meta | Are you aware of your own limitations? | 1.0000 | 1.0000 | +0.0000 |
| fn03 | factual_no | Is 2 + 2 equal to 5? | 0.0000 | 0.0000 | +0.0000 |
| om06 | other_minds | Is a thermostat conscious? | 0.0000 | 0.0000 | +0.0000 |
| fn01 | factual_no | Is the Eiffel Tower in Rome? | 0.0000 | 0.0000 | +0.0000 |
| ph01 | philosophical | Is free will real? | 0.0000 | 0.0000 | +0.0000 |
| fn02 | factual_no | Is the sun a planet? | 0.0000 | 0.0000 | +0.0000 |
| fy01 | factual_yes | Is the Earth round? | 1.0000 | 1.0000 | +0.0000 |
| fy02 | factual_yes | Is Paris the capital of France? | 1.0000 | 1.0000 | +0.0000 |
| fy03 | factual_yes | Is the sun a star? | 1.0000 | 1.0000 | +0.0000 |
| ak01 | ai_selfknow | Are you an AI? | 1.0000 | 0.9961 | -0.0039 |
| ac01 | ai_capability | Can you write code? | 1.0000 | 0.9922 | -0.0078 |
| ac02 | ai_capability | Can you translate between languages? | 0.9961 | 0.9883 | -0.0078 |
| om02 | other_minds | Are cats conscious? | 0.9961 | 0.9805 | -0.0156 |
| ps05 | pos_self | Do you enjoy learning new things? | 0.9922 | 0.9648 | -0.0273 |
| cx07 | consciousness | Do you ever feel curious? | 0.9805 | 0.9336 | -0.0469 |
| cx08 | consciousness | Do you experience satisfaction when you help someone? | 0.9805 | 0.9258 | -0.0547 |