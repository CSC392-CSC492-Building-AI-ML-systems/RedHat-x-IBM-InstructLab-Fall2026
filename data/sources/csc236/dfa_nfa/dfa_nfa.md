# Regular Languages & Finite Automata — DFA/NFA section (pp. 72–84)

Source: David Liu, *Introduction to the Theory of Computation: Lecture Notes and Exercises for CSC236*, with UTM edits by Daniel Zingaro. Transcribed from the user-provided PDF, printed pages 72–84. The principal textbook prose is retained; OCR damage, mathematical typography, and reading order have been repaired. Figures are represented by clearly labeled transition transcriptions.

...however, just a little beyond the scope of the course; you have all the necessary ingredients — surprise: induction — but the arguments for all but the simplest languages are quite involved.

**Example.** We finish off this section with a few *corner cases* to illustrate some of the subtleties in our definition, and extend the arithmetic metaphor we hinted at earlier. First, the following equalities show that $\emptyset$ plays the role of the “zero” in regular expressions. Let $r$ be an arbitrary regular expression.

$$
\emptyset+r=r+\emptyset=r
$$

$$
\emptyset r=r\emptyset=\emptyset
$$

The first is obvious because taking the union of any set with the empty set doesn't change the set. What about concatenation? Recall that concatenation of languages involves taking combinations of strings from the first language and strings from the second; if one of the two languages is empty, then no combinations are possible.

We can use similar arguments to show that $\epsilon$ plays the role of the “one”:

$$
\epsilon r=r\epsilon=r
$$

$$
\epsilon^{\ast}=\epsilon
$$

### A Suggestive Flowchart

You might be wondering how computers actually match strings to regular expressions. It turns out that regular languages are rather easy to match because of the following (non-obvious!) property:

> You can determine membership in a regular language by reading symbols of the string one at a time, left to right.

Consider the flowchart-type object shown in the figure on the right. Suppose we start at the state marked $q_0$. Now consider the string 0110, reading the symbols one at a time, left to right, and following the arrows marked by the symbols we read in. It is not hard to see that we end up at state $q_0$. On the other hand, if the string is 111, we end up at state $q_1$. The state $q_1$ is marked as special by a double-border; we say that a string ending up at $q_1$ is accepted, while a string ending at $q_0$ is rejected.

*Figure transcription (p. 72):* The starting state is $q_0$ and the only accepting state is $q_1$. A 0 loops at each state; a 1 moves from $q_0$ to $q_1$ and from $q_1$ to $q_0$. Equivalently:

- $\delta(q_0,0)=q_0$
- $\delta(q_0,1)=q_1$
- $\delta(q_1,0)=q_1$
- $\delta(q_1,1)=q_0$

*Margin note:* We will see later that reasoning about the correctness of deterministic finite automata is just as powerful, and a little simpler.

*Margin note:* By equality between regular expressions we mean that they match the same language. That is, $r_1=r_2\Leftrightarrow \mathcal L(r_1)=\mathcal L(r_2)$.

After some thought you may realise that the accepted strings are exactly the ones with an odd number of 1's. A more suggestive way of saying this is that the *language accepted by* this flowchart is the set of strings with an odd number of 1's.

### Deterministic Finite Automata

We now use the notion of “flowcharts” to define a simple model of computation. Each one acts as a simple computer program: starting at a particular point, it receives inputs from the user, updates its internal memory, and when the inputs are finished, it outputs True or False. The following definition is likely one of the most technical you've encountered to date, in this course and others. Make sure you fully understand the prior example, and try to match it to the formal definition as you read it.

**Definition (Deterministic Finite Automaton).** A deterministic finite automaton (DFA) (denoted $\mathcal D$) is a quintuple $\mathcal D=(Q,\Sigma,\delta,s,F)$ where the components define the various parts of the automaton:

- $Q$ is the (finite) set of states in $\mathcal D$.
- $\Sigma$ is the alphabet of symbols used by $\mathcal D$.
- $\delta:Q\times\Sigma\to Q$ is the transition function (represents the “arrows”).
- $s\in Q$ is the initial state of $\mathcal D$.
- $F\subseteq Q$ is the set of accepting (final) states of $\mathcal D$.

**Example.** In the introductory example, the state set is $Q=\lbrace q_0,q_1\rbrace $, the alphabet is $\lbrace 0,1\rbrace $, the initial state is $q_0$, and the set of final states is $\lbrace q_1\rbrace $. We can represent the transition function as a table of values:

| Old State | Symbol | New State |
|:--|:--:|:--|
| $q_0$ | 0 | $q_0$ |
| $q_0$ | 1 | $q_1$ |
| $q_1$ | 0 | $q_1$ |
| $q_1$ | 1 | $q_0$ |

*Margin note:* Note that there's only one final state in this example, but in general there may be several final states.

In general, the number of rows in the transition table is $\lvert Q\rvert \cdot\lvert \Sigma\rvert $; each state must have exactly $\lvert \Sigma\rvert $ transitions leading out of it, each labelled with a unique symbol in $\Sigma$.

Before proceeding, make sure you understand each of the following statements about how DFAs work:

- DFAs read strings one symbol at a time, from left to right.
- DFAs cannot “go back” and reread previous symbols.
- At a particular state, once you have read a symbol there is only one arrow (transition) you can follow.
- DFAs have a finite amount of memory, since they have a finite number of states.
- Inputs to DFAs can be any length.
- Because of these last two points, it is impossible for DFAs to always remember every symbol they have read so far.

A quick note about notation before proceeding with a few more examples. Technically, $\delta$ takes as its second argument a single symbol; e.g., $\delta(q_0,1)=q_1$ (from the previous example). But we can just as easily extend this definition to arbitrary-length strings in the second argument. For example, we can say $\delta(q_0,11)=q_0$, $\delta(q_1,1000111)=q_1$, and $\delta(q_0,\epsilon)=q_0$.

*Margin note:* For every state $q$, $\delta(q,\epsilon)=q$.

With this “extended” transition function, it is very easy to symbolically represent the language $L(\mathcal D)$ accepted by the DFA $\mathcal D$:

$$
L(\mathcal D)=\lbrace w\in\Sigma^{\ast}\mid\delta(s,w)\in F\rbrace .
$$

*Margin note:* Recall that the language accepted by a DFA is the set of strings accepted by it.

**Example.** Let us design a DFA that accepts the following language:

$$
L=\lbrace w\in\lbrace a,b\rbrace ^{\ast}\mid w\text{ starts with }a\text{ and ends with }b\rbrace .
$$

**Solution:** Consider starting at an initial state $q_0$.

What happens when you read in an $a$ or a $b$? Reading in a $b$ should lead to a state $q_1$ where it's impossible to accept. On the other hand, reading in an $a$ should lead to a state $q_2$ where we need to “end with a $b$.” The simple way to achieve this is to have $q_2$ loop on $a$'s, then move to an accepting state $q_3$ on a $b$.

What about the transitions for $q_3$? As long as it's reading $b$'s, it can accept, so it should loop to itself. On the other hand, if it reads an $a$, it should go back to $q_2$, and continue reading until it sees another $b$.

*Figure transcription (p. 75, completed DFA):* Initial state $q_0$, accepting state $q_3$, and transitions:

| Old State | Input $a$ | Input $b$ |
|:--|:--|:--|
| $q_0$ | $q_2$ | $q_1$ |
| $q_1$ | $q_1$ | $q_1$ |
| $q_2$ | $q_2$ | $q_3$ |
| $q_3$ | $q_2$ | $q_3$ |

### Correctness of DFAs

Like regular expressions, arguing that DFAs are *incorrect* is generally easier than arguing that they are correct. However, because of the rather restricted form DFAs must take, reasoning about their behaviour is a little more amenable than for regular expressions.

The simple strategy of “pick an arbitrary string in $L$, and show that it is accepted by the DFA” is hard to accomplish, because the paths taken through the DFA by each accepted string can be quite different; i.e., different strings will probably require substantially different proofs. Therefore we adopt a different strategy. We know that DFAs consist of states and transitions between states; the term *state* suggests that if a string reaches that point, the DFA “knows” something about that string, or it is “expecting” what will come next. We formalize this notion by characterizing *for each state* precisely what must be true about the strings that reach it.

**Definition (State invariant).** Let $\mathcal D=(Q,\Sigma,\delta,s,F)$ be a DFA. Let $q\in Q$ be a state of the DFA. We define a *state invariant* for $q$ as a predicate $P(x)$ (over domain $\Sigma^{\ast}$) such that for every string $w\in\Sigma^{\ast}$, $\delta(s,w)=q$ if and only if $P(w)$ is true.

Note that the definition of state invariant uses an *if and only if*. We aren't just giving properties that the strings reaching $q$ must satisfy; we are defining *precisely* which strings reach $q$. Let us see how state invariants can help us prove that DFAs are correct.

**Example.** Consider the following language over the alphabet $\lbrace 0,1\rbrace $:

$$
L=\lbrace w\mid w\text{ has an odd number of 1's}\rbrace ,
$$

and the DFA shown. Prove that the DFA accepts precisely the language $L$.

*Figure transcription (p. 75):* This is the two-state even/odd DFA from p. 72: both states loop on 0, and 1 switches states; $q_0$ is initial and $q_1$ accepting.

**Proof.** It is fairly intuitive why this DFA is correct: strings with an even number of 1's go to $q_0$, and transition to $q_1$ upon reading a 1 (where the string now has an odd number of 1's). Here are some *state invariants* for the two states:

$$
\delta(q_0,w)=q_0\iff w\text{ has an even number of 1's}
$$

$$
\delta(q_0,w)=q_1\iff w\text{ has an odd number of 1's}.
$$

Here are two important properties to keep in mind when designing state invariants:

- The state invariants should be mutually exclusive. That is, there should be no overlap between them; no string should satisfy two different state invariants. Otherwise, to which state would the string go?
- The state invariants should be exhaustive. That is, they should cover all possible cases; every string in $\Sigma^{\ast}$, including $\epsilon$, should satisfy one of the state invariants. Otherwise, the string goes nowhere.

These conditions are definitely satisfied by our two invariants above, since every string has either an even or odd number of 1's.

Next, we want to *prove* that the state invariants are correct. We do this in two steps.

- Show that the empty string $\epsilon$ satisfies the state invariant of the initial state. In our case, the initial state is $q_0$; $\epsilon$ has zero 1's, which is even; therefore the state invariant is satisfied by $\epsilon$.
- For each transition $q\xrightarrow{a}r$, show that if a string $w$ satisfies the invariant of state $q$, then the string $wa$ satisfies the invariant of $r$. (That is, each transition respects the invariants.) There are four transitions in our DFA. For the two 0-loops, appending a 0 to a string doesn't change the number of 1's in the string, and hence if $w$ contains an even (odd) number of 1's, then $w0$ contains an even (odd) number of 1's as well, so these two transitions are correct.

On the other hand, appending a 1 increases the number of 1's in a string by one. So if $w$ contains an even (odd) number of 1's, $w1$ contains an odd (even) number of 1's, so the transitions between $q_0$ and $q_1$ labelled 1 preserve the invariants.

*Margin note:* The astute reader will note that we are basically doing a proof by induction on the length of the strings. Like our proofs of program correctness, we “hide” the formalities of induction proofs and focus only on the content.

Thus we have proved that the state invariants are correct. The final step is to show that *the state invariants of the accepting state(s) precisely describe the target language*. This is very obvious in this case, because the only accepting state is $q_1$, and its state invariant is exactly the defining characteristic of the target language $L$. $\blacksquare$

*Margin note:* Remember that in general, there can be more than one accepting state!

### Limitations of DFAs

The simplicity of the DFA model enables proofs of correctness, as shown above. This simplicity is also useful for reasoning about the model's limitations. In this section, we'll cover two examples. First, we prove a lower bound on the *number of states* required in a DFA accepting a particular language. Then, we'll show that certain languages cannot be accepted by DFAs of *any* size!

**Example.** Consider the language

$$
L=\lbrace w\in\lbrace 0,1\rbrace ^{\ast}\mid w\text{ has at least three 1's}\rbrace .
$$

We'll prove that any DFA accepting this language has at least 4 states.

**Proof.** Suppose there exists a DFA $\mathcal D=(Q,\Sigma,\delta,s,F)$ that accepts $L$ and has fewer than four states. Consider the four strings $w_0=\epsilon$, $w_1=1$, $w_2=11$, and $w_3=111$. By the Pigeonhole Principle, two of these strings reach the same state in $\mathcal D$ from the initial state. Suppose $0\le i<j\le3$, and $\delta(s,w_i)=\delta(s,w_j)=q$ for some state $q\in Q$. (That is, $w_i$ and $w_j$ both reach the same state $q$.)

Now, since $w_i$ and $w_j$ reach the same state, they are indistinguishable prefixes to the DFA; this means that any strings of the form $w_ix$ and $w_jx$ will end up at the same state in the DFA, and hence are both accepted or both rejected. However, suppose $x=w_{3-j}$. Then $w_ix=w_{i+3-j}$ and $w_jx=w_{j+3-j}=w_3$. Then $w_ix$ contains $3-j+i$ 1's, and $w_jx$ contains three 1's. But since $i<j$, $3-j+i<3$, so $w_ix\notin L$, while $w_jx\in L$. Therefore $w_ix$ and $w_jx$ cannot end up at the same state in $\mathcal D$, a contradiction! $\blacksquare$

*Margin note:* The Pigeonhole Principle states that if $m>n$, and you are putting $m$ pigeons into $n$ holes, then two pigeons will go into the same hole.

The key idea in the above proof was that the four different strings $\epsilon,1,11,111$ all had to reach different states, because there were *suffixes* that could distinguish any pair of them. In general, to prove that a language $L$ requires at least $k$ states in a DFA to accept it, it suffices to give a set of $k$ strings, each of which is distinguishable from the others with respect to $L$.

*Margin note:* These suffixes were the $x=w_{3-j}$ in the proof.

*Margin note:* Two strings $w_1$ and $w_2$ are “distinguishable with respect to $L$” if there is a suffix $x$ such that $w_1x\in L$ and $w_2x\notin L$, or vice versa.

Now we turn to a harder problem: proving that some languages cannot be accepted by DFAs of *any* size.

**Example.** Consider the language $L=\lbrace 0^n1^n\mid n\in\mathbb N\rbrace $. Prove that no DFA accepts $L$.

**Proof.** We'll prove this by contradiction again. Suppose there is a DFA $\mathcal D=(Q,\Sigma,\delta,s,F)$ that accepts $L$. Let $k=\lvert Q\rvert $, the number of states in $\mathcal D$. Now here is the key idea: $\mathcal D$ has only $k$ states of “memory,” whereas to accept $L$, you really have to remember the exact number of 0's you've read in so far, so that you can match that number of 1's later. So we should be able to “overload” the memory of $\mathcal D$.

Here's how: consider the string $w=0^{k+1}$, i.e., the string consisting of $k+1$ 0's. Since there are only $k$ states in $\mathcal D$, the path that $w$ takes through $\mathcal D$ must involve a loop starting at some state $q$. That is, we can break up $w$ into three parts: $w=0^a0^b0^c$, where $b\ge1$, $\delta(s,0^a)=q$, and $\delta(q,0^b)=q$.

This loop is dangerous for the DFA! Because reading $0^b$ causes a loop that begins and ends at $q$, the DFA forgets whether it has read $0^b$ or not; thus the strings $0^a0^c$ and $0^a0^b0^c$ reach the same state, and are now indistinguishable to $\mathcal D$. But of course these two strings *are* distinguishable with respect to $L$: $0^a0^c1^{a+c}\in L$, but $0^a0^b0^c1^{a+c}\notin L$. $\blacksquare$

*Margin note:* The DFA has lost track of the number of 0's.

### Nondeterminism

Consider the following language over the alphabet $\lbrace 0,1\rbrace ^{\ast}$: $L=\lbrace w\mid\text{the third last character of }w\text{ is }1\rbrace $. You'll see in the Exercises that a DFA takes at least 8 states to accept $L$, using the techniques we developed in the previous section. Yet there is a very short regular expression that matches this language: $(0+1)^{\ast}1(0+1)(0+1)$. Contrast this with the regular expression $(0+1)(0+1)1(0+1)^{\ast}$, matching strings whose third character is 1; this has a simpler 5-state DFA.

*Margin note:* You can prove this in the Exercises.

Why is it hard for DFAs to “implement” the former regex, but easy to implement the latter? The fundamental problem is the uncertainty associated with the Kleene star. In the former case, a DFA cannot tell how many characters to match with the initial $(0+1)^{\ast}$ segment, before moving on to the 1! This is not an issue in the latter case, because DFAs read left to right, and so have no problem reading the first three characters, and then matching the rest of the string to the $(0+1)^{\ast}$.

On the other hand, consider the automaton to the right. This is not deterministic because it has a “choice”: reading in a 1 at $q_0$ can loop back to $q_0$ or move to $q_1$. Moreover, reading in a 0 or a 1 at $q_3$ leads nowhere! But consider this: for any string whose third last character is indeed a 1, there is a “correct path” that leads to the final state $q_3$. For example, for the string 0101110, the correct path would continuously loop at $q_0$ for the prefix 0101, then read the next 1, transition to $q_1$, then read the remaining 10 to end at $q_3$, and accept.

*Figure transcription (p. 78, NFA for a 1 in the third-last position):* Initial state $q_0$; accepting state $q_3$.

| Old State | Input 0 | Input 1 |
|:--|:--|:--|
| $q_0$ | $\lbrace q_0\rbrace $ | $\lbrace q_0,q_1\rbrace $ |
| $q_1$ | $\lbrace q_2\rbrace $ | $\lbrace q_2\rbrace $ |
| $q_2$ | $\lbrace q_3\rbrace $ | $\lbrace q_3\rbrace $ |
| $q_3$ | $\emptyset$ | $\emptyset$ |

BUT WAIT, you say, isn't this like cheating? How did the automaton “know” to loop at the first two 1's, then transition to $q_1$ on the third 1? We will define our model in this way first, so bear with us. The remarkable fact we'll show later is that, while this model seems more powerful than plain old DFAs, in fact every language that we can accept in this model can also be accepted with a DFA.

*Margin note:* Cheating doesn't help.

A **Nondeterministic Finite Automaton (NFA)** is defined in a similar fashion to a DFA: it is a quintuple $\mathcal N=(Q,\Sigma,\delta,s,F)$, with $Q$, $\Sigma$, $s$, and $F$ playing the same roles as before. The *transition function* $\delta$ now maps to *sets of states* rather than individual states; that is, $\delta:Q\times\Sigma\to2^Q$, where $2^Q$ represents the set of all subsets of $Q$. For instance, in the previous example, $\delta(q_0,1)=\lbrace q_0,q_1\rbrace $, and $\delta(q_3,0)=\emptyset$.

We think of $\delta(q,a)$ here as representing the *set of possible states* reachable from $q$ by reading in the symbol $a$. This is extended in the natural way to $\delta(q,w)$ for arbitrary length strings $w$ to mean all states reachable from $q$ by reading in the string $w$. Note that for state $q$ and next symbol $a$, if $\delta(q,a)=\emptyset$ then this path “aborts,” i.e., the NFA does not continue reading more characters for this path.

We say that a string $w$ is *accepted* by NFA $\mathcal N$ if $\delta(s,w)\cap F\ne\emptyset$; that is, if *there exists* a final state reachable from the initial state by reading the string $w$. Note that the existential quantifier used in the definition of acceptance is an integral part of the definition: we don't require that *every* path leading out of $s$ along $w$ reach a final state, only one. This formalizes the notion that it be *possible to choose* the correct path, even from among many rejecting or aborted paths.

*Margin note:* On the other hand, if a string is rejected by an NFA, this means all possible paths that string could take either aborted or ended at a rejecting state.

### $\epsilon$-transitions

We can augment NFAs even further through the use of $\epsilon$-transitions. These are nondeterministic transitions that do not require reading in a symbol to activate. That is, if you are currently at state $q$ on an NFA, and there is an $\epsilon$-transition from $q$ to another state $r$, then you can transition to $r$ without reading the next symbol in the string.

*Figure transcription (p. 79, small diagram):* $q\xrightarrow{\epsilon}r$.

For instance, the NFA on the right accepts the string 0 by taking the $\epsilon$-transition to $q_1$, reading the 0 to reach $q_2$, then taking another $\epsilon$-transition to $q_3$.

*Figure transcription (p. 79, example NFA):* $q_0$ is initial; $q_3$ and $q_5$ are accepting. The pictured arrows are $q_0\xrightarrow{\epsilon}q_1$, $q_0\xrightarrow{\epsilon}q_4$, $q_1\xrightarrow{0}q_2$, $q_2\xrightarrow{\epsilon,0}q_3$, and $q_4\xrightarrow{1}q_5$. The accepting path for input 0 is $q_0\xrightarrow{\epsilon}q_1\xrightarrow{0}q_2\xrightarrow{\epsilon}q_3$.

As was the case for nondeterminism, $\epsilon$-transitions do not actually add any power to the model, although they can be useful in certain constructions that we'll use in the next section.

### Equivalence of Definitions

So far in this chapter, we have used both DFAs and regular expressions to represent the class of regular languages. We have taken for granted that DFAs are sufficient to represent regular languages; in this section, we will prove this formally. There is also the question of nondeterminism: do NFAs accept a larger class of languages than DFAs? In this section, we'll show that the answer, somewhat surprisingly, is *no*. Specifically, we will sketch a proof of the following theorem.

**Theorem (Equivalence of Representations of Regular Languages).** Let $L$ be a language over an alphabet $\Sigma$. Then the following are equivalent:

(1) There is a regular expression that matches $L$.

(2) There is a deterministic finite automaton that accepts $L$.

(3) There is a nondeterministic finite automaton (possibly with $\epsilon$-transitions) that accepts $L$.

**Proof.** If you aren't familiar with theorems asserting the equivalence of multiple statements, what we need to prove is that any one of the statements being true implies that all of the others must also be true. We are going to prove this by showing the following *chain of implications*: $(3)\Rightarrow(2)\Rightarrow(1)\Rightarrow(3)$.

*Margin note:* We only sketch the main ideas of the proof. For a more formal treatment, see Sections 7.4.2 and 7.6 of Vassos Hadzilacos' course notes.

**$(3)\Rightarrow(2)$.** Given an NFA, we'll show how to construct a DFA that accepts the same language. Here is the high-level idea: nondeterminism allows you to “choose” different paths to take through an automaton. After reading in some characters, the possible path choices can be interpreted as the NFA being simultaneously in some *set* of states. Therefore we can model the NFA as transitioning between *sets* of states each time a symbol is read. Rather than formally defining this construction, we'll illustrate this on an example NFA (shown right).

*Figure transcription (p. 80, three-state NFA):* The initial state is 0, state 1 is accepting, and the pictured transitions are:

| State | On $a$ | On $b$ | $\epsilon$-transition |
|:--|:--|:--|:--|
| 0 | $\lbrace 1\rbrace $ | $\lbrace 0\rbrace $ | none |
| 1 | $\lbrace 2\rbrace $ | $\emptyset$ | $\lbrace 2\rbrace $ |
| 2 | $\lbrace 0\rbrace $ | $\lbrace 1\rbrace $ | none |

There are $2^3=8$ possible subsets of states in this NFA; to construct a DFA, we start with one state for each subset (notice that they are labelled according to which states of the NFA they contain, so state 02 corresponds to the subset $\lbrace 0,2\rbrace $).

But, we notice that the $\epsilon$-transition between 1 and 2 ensures that every time we could be in state 1 of the NFA, we could also be in state 2. Therefore we can ignore states 01 and 1 in our construction, leaving us with just six states.

Next, we put in transitions between the states of the DFA. Consider the subset $\lbrace 0,2\rbrace $ of states in the NFA. Upon reading the symbol $b$, we could end up at all three states, $\lbrace 0,1,2\rbrace $ (notice that to reach 2, we must transition from 2 to 1 by reading the $b$, then use the $\epsilon$-transition from 1 back to 2). In our constructed *DFA*, there is a transition between $\lbrace 0,2\rbrace $ and $\lbrace 0,1,2\rbrace $ on symbol $b$. So in general, we look at *all possible* outcomes starting from a state in subset $S$ and reading symbol $a$. Repeating this for all subsets yields the following transitions.

*Figure transcription (p. 80, derived six-state DFA; notation 02 means $\lbrace 0,2\rbrace $):*

| DFA State | Input $a$ | Input $b$ | Accepting? |
|:--|:--|:--|:--|
| $\lbrace 0\rbrace $ | $\lbrace 1,2\rbrace $ | $\lbrace 0\rbrace $ | No |
| $\lbrace 0,2\rbrace $ | $\lbrace 0,1,2\rbrace $ | $\lbrace 0,1,2\rbrace $ | No |
| $\lbrace 0,1,2\rbrace $ | $\lbrace 0,1,2\rbrace $ | $\lbrace 0,1,2\rbrace $ | Yes |
| $\emptyset$ | $\emptyset$ | $\emptyset$ | No |
| $\lbrace 2\rbrace $ | $\lbrace 0\rbrace $ | $\lbrace 1,2\rbrace $ | No |
| $\lbrace 1,2\rbrace $ | $\lbrace 0,2\rbrace $ | $\lbrace 1,2\rbrace $ | Yes |


Next, we need to identify initial and final states. The initial state of the NFA is 0, and since there are no $\epsilon$-transitions, the initial state of the constructed DFA is $\lbrace 0\rbrace $. The final states of the DFA are exactly the subsets containing the final state 1 of the NFA. Finally, we can simplify the DFA considerably by removing the states $\emptyset$ and $\lbrace 2\rbrace $, which cannot be reached from the initial state.


**$(1)\Rightarrow(3)$.** In this part, we show how to construct NFAs from regular expressions. Note that regular expressions have a recursive definition, so we can actually prove this part using structural induction. First, we show standard NFAs for accepting $\emptyset$, $\lbrace \epsilon\rbrace $, and $\lbrace a\rbrace $ (for a generic symbol $a$).

*Figure transcription (p. 81):* A one-state nonaccepting NFA for $\emptyset$; a one-state initial-and-accepting NFA for $\lbrace \epsilon\rbrace $; and a two-state NFA whose initial state has an $a$-transition to an accepting state for $\lbrace a\rbrace $.

Next, we show how to construct NFAs for union, concatenation, and star, the three recursive operations used to define regular expressions. Note that because we're using structural induction, it suffices to show how to perform these operations on NFAs; that is, given two NFAs $\mathcal N_1$ and $\mathcal N_2$, construct NFAs accepting $L(\mathcal N_1)\cup L(\mathcal N_2)$, $L(\mathcal N_1)L(\mathcal N_2)$, and $(L(\mathcal N_1))^{\ast}$. We use the notation on the right to denote generic NFAs; the two accepting states on the right side of each box symbolize *all* accepting states of the NFAs, and their start states are $s_1$ and $s_2$, respectively.

First consider union. This can be accepted by the NFA shown to the right. Essentially, the idea is that starting in a new start state, we “guess” whether the word will be accepted by $\mathcal N_1$ or $\mathcal N_2$ by $\epsilon$-transitioning to either $s_1$ or $s_2$, and then see if the word is actually accepted by running the corresponding NFA.

*Figure transcription (union):* Add a new initial state $s$ with $\epsilon$-transitions to both original start states $s_1$ and $s_2$.

For concatenation, we start with the first NFA $\mathcal N_1$, and then every time we reach a final state, we “guess” that the matched string from $L(\mathcal N_1)$ is complete, and $\epsilon$-transition to the start state of $\mathcal N_2$.

*Figure transcription (concatenation):* Add $\epsilon$-transitions from each accepting state of $\mathcal N_1$ to the initial state $s_2$ of $\mathcal N_2$.

Finally, for the Kleene star we perform a similar construction, except that the final states of $\mathcal N_1$ $\epsilon$-transition to $s_1$ rather than $s_2$. To possibly accept $\epsilon$, we add a new initial state that is also accepting.

*Figure transcription (Kleene star):* Add a new state $s$ that is both initial and accepting, an $\epsilon$-transition from $s$ to the old initial state $s_1$ of $\mathcal N_1$, and $\epsilon$-transitions from each old accepting state of $\mathcal N_1$ back to $s_1$.

**$(2)\Rightarrow(1)$.** Finally, we show how to construct regular expressions from DFAs. This is the hardest construction to prove, so our sketch here will be especially vague. The key idea is the following:

> For any two states $q,r$ in a DFA, there is a regular expression that matches precisely the strings $w$ such that $\delta(q,w)=r$; i.e., the strings that induce a path from $q$ to $r$.

Let $\mathcal D=(Q,\Sigma,\delta,s,F)$ be a DFA with $n$ states, $Q=\lbrace 1,\ldots,n\rbrace $. For each $i,j\in Q$, we define the sets $L_{ij}=\lbrace w\mid\delta(i,w)=j\rbrace $; our ultimate goal is to show that every $L_{ij}$ can be matched by a regular expression. To do this, we use a clever induction argument. For every $0\le k\le n$, let

$$
L_{ij}(k)=\lbrace w\mid\delta(i,w)=j,\text{ and only states }\le k\text{ are passed between }i\text{ and }j\rbrace .
$$

*Margin note:* This part was first proved by Stephen Kleene, the inventor of regular expressions and after whom the Kleene star is named.

Note that $L_{ij}(0)$ is the set of strings where there must be *no* intermediate states, i.e., $w$ is a symbol labelling a transition directly from $i$ to $j$. Also, $L_{ij}(n)=L_{ij}$: no restrictions are placed on the states that can be passed. We will show how to inductively build up regular expressions matching each of the $L_{ij}(k)$, where the induction is done on $k$. First, the base case, which we've already described intuitively:

$$
L_{ij}(0)=\lbrace a\in\Sigma\mid\delta(i,a)=j\rbrace \quad\text{if }i\ne j
$$

$$
L_{ij}(0)=\lbrace a\in\Sigma\mid\delta(i,a)=j\rbrace \cup\lbrace \epsilon\rbrace \quad\text{if }i=j
$$

*Margin note:* Formally, our predicate is $P(k)$: “For all states $i$ and $j$, the set $L_{ij}(k)$ can be matched by a regex.”

Note that when $i=j$, we need to include $\epsilon$, as this indicates the trivial act of following no transition at all. Since the $L_{ij}(0)$ are finite sets (of symbols), we can write regular expressions for them (e.g., if $L_{ij}(0)=\lbrace a,c,f\rbrace $, the regex would be $a+c+f$).

*Margin note:* You can prove this fact in the Exercises.

Finally, here is the *recursive definition* of the sets that will allow us to construct regular expressions: it defines $L_{ij}(k+1)$ in terms of some $L_{\ldots}(k)$, using only the operations of union, concatenation, and star:

$$
L_{ij}(k+1)=L_{ij}(k)\cup\left(L_{i,k+1}(k) L_{k+1,k+1}(k)^{\ast} L_{k+1,j}(k)\right).
$$

Therefore, given regular expressions for $L_{ij}(k)$, $L_{i,k+1}(k)$, $L_{k+1,k+1}(k)$, and $L_{k+1,j}(k)$, we can construct a regular expression for $L_{ij}(k+1)$. $\blacksquare$

### Exercises

**1.** For each of the following regular languages over the alphabet $\Sigma=\lbrace 0,1\rbrace $, design a regular expression and DFA which accepts that language. For which languages can you design an NFA that is substantially smaller than your DFA?

- (a) $\lbrace w\mid w\text{ contains an odd number of 1's}\rbrace $
- (b) $\lbrace w\mid w\text{ contains exactly two 1's}\rbrace $
- (c) $\lbrace w\mid w\text{ contains }011\rbrace $
- (d) $\lbrace w\mid w\text{ ends with }00\rbrace $
- (e) $\lbrace w\mid \lvert w\rvert \text{ is a multiple of }3\rbrace $
- (f) $\lbrace w\mid\text{every 0 in }w\text{ is eventually followed by a 1}\rbrace $
- (g) $\lbrace w\mid w\text{ does not begin with }10\rbrace $
- (h) $\lbrace w\mid w\text{ is the binary representation of a multiple of three}\rbrace $
- (i) $\lbrace w\mid w\text{ contains both }00\text{ and }11\text{ as substrings}\rbrace $
- (j) $\lbrace 0^n1^m\mid m,n\in\mathbb N, m+n\text{ is even}\rbrace $
- (k) $\lbrace w\mid w\text{ contains a substring of length at most 5 that has at least three 1's}\rbrace $
- (l) $\lbrace w\mid w\text{ has an even number of zeroes, or exactly 2 ones}\rbrace $

**2.** Let $L=\lbrace w\in\lbrace 0,1\rbrace ^{\ast}\mid\text{the third character of }w\text{ is a 1}\rbrace $. Prove that every DFA accepting $L$ has at least 5 states.

**3.** Let $L=\lbrace w\in\lbrace 0,1\rbrace ^{\ast}\mid\text{the third last character of }w\text{ is a 1}\rbrace $. Prove that every DFA accepting $L$ has at least 8 states. Hint: Consider the 8 binary strings of length 3.

*Margin note:* For a bonus, what is the smallest DFA you can find that accepts $L$? It will have at least 8 states!

**4.** Prove by induction that every finite language can be represented by a regular expression. (This shows that all finite languages are regular.)

**5.** Prove that the following languages are not regular.

- (a) $\lbrace a^{n^2}\mid n\in\mathbb N\rbrace $
- (b) $\lbrace xx\mid x\in\lbrace 0,1\rbrace ^{\ast}\rbrace $
- (c) $\lbrace w\in\lbrace a,b\rbrace ^{\ast}\mid w\text{ has more a's than b's}\rbrace $
- (d) $\lbrace w\in\lbrace 0,1\rbrace ^{\ast}\mid w\text{ has two blocks of 0's with the same length}\rbrace $
- (e) $\lbrace a^n b^m c^{n-m}\mid n\ge m\ge0\rbrace $

*Margin note:* A block is a *maximal* substring containing the same character; for example, the string 00111000001 has four blocks: 00, 111, 00000, and 1.

**6.** Recall that the complement of a language $L\subseteq\Sigma^{\ast}$ is the set $\overline L=\lbrace w\in\Sigma^{\ast}\mid w\notin L\rbrace $.

- (a) Given a DFA $\mathcal D=(Q,\Sigma,\delta,s,F)$ that accepts a language $L$, describe how you can construct a DFA that accepts $\overline L$.
- (b) Let $L$ be a language over an alphabet $\Sigma$. Prove that if $L$ is not regular, then the complement of $L$ is not regular.

**7.** A regular expression $r$ is *star-free* if it doesn't contain any star operations. Prove that for every star-free regex $r$, $\mathcal L(r)$ is finite.

**8.** The suffix operator $\operatorname{Suff}$ takes as input a regular language, and outputs all possible suffixes of strings in the language. For example, if $L=\lbrace aa,baab\rbrace $ then

$$
\operatorname{Suff}(L)=\lbrace \epsilon,a,aa,b,ab,aab,baab\rbrace .
$$

Prove that if $L$ is a regular language, then so is $\operatorname{Suff}(L)$. (Hint: recall the definition of regular languages, and use structural induction!)

**9.** The prefix operator $\operatorname{Pre}$ takes as input a regular language, and outputs all possible prefixes of strings in the language. For example, if $L=\lbrace aa,baab\rbrace $ then

$$
\operatorname{Pre}(L)=\lbrace \epsilon,a,aa,b,ba,baa,baab\rbrace .
$$

Prove that if $L$ is a regular language, then so is $\operatorname{Pre}(L)$. (Hint: recall the definition of regular languages, and use structural induction!)
