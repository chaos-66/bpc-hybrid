import edu.stanford.nlp.trees.Tree;
import edu.stanford.nlp.trees.tregex.TregexMatcher;
import edu.stanford.nlp.trees.tregex.TregexPattern;
import edu.stanford.nlp.trees.tregex.tsurgeon.Tsurgeon;
import edu.stanford.nlp.trees.tregex.tsurgeon.TsurgeonPattern;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Small-pipeline bridge for Sun et al. Section 4.2.2.
 *
 * <p>Modality, condition, constraint, exception, and actor are captured from
 * the same original tree.  A separate copy is then pruned for the sole purpose
 * of applying the published final action rule to every remaining VP.  Thus an
 * outer condition cannot erase an inner exception before the exception rule is
 * observed.</p>
 */
public final class SunPaperIndependentContextBridge {
  private static final class Rule {
    final String field;
    final TregexPattern pattern;
    final TsurgeonPattern operation;

    Rule(String field, TregexPattern pattern, TsurgeonPattern operation) {
      this.field = field;
      this.pattern = pattern;
      this.operation = operation;
    }
  }

  private SunPaperIndependentContextBridge() {}

  private static List<Rule> loadRules(Path path) throws Exception {
    List<Rule> rules = new ArrayList<>();
    for (String raw : Files.readAllLines(path, StandardCharsets.UTF_8)) {
      if (raw.trim().isEmpty()) continue;
      String[] parts = raw.split("\\t", -1);
      if (parts.length != 3) throw new IllegalArgumentException("invalid rule-plan line");
      rules.add(new Rule(
          parts[0],
          TregexPattern.compile(parts[1]),
          parts[2].trim().isEmpty() ? null : Tsurgeon.parseOperation(parts[2])));
    }
    if (rules.isEmpty()) throw new IllegalArgumentException("rule plan is empty");
    return rules;
  }

  private static Map<String, List<Rule>> groupRules(List<Rule> rules) {
    Map<String, List<Rule>> grouped = new LinkedHashMap<>();
    for (Rule rule : rules) {
      grouped.computeIfAbsent(rule.field, ignored -> new ArrayList<>()).add(rule);
    }
    return grouped;
  }

  private static String nodeText(Tree node) {
    List<String> words = new ArrayList<>();
    for (Tree leaf : node.getLeaves()) words.add(leaf.label().value());
    return String.join(" ", words).replace('\t', ' ').replace('\n', ' ');
  }

  private static int[] originalSpan(Tree node, IdentityHashMap<Tree, Integer> indexes) {
    List<Tree> leaves = node.getLeaves();
    if (leaves.isEmpty()) throw new IllegalStateException("matched node has no leaves");
    Integer begin = indexes.get(leaves.get(0));
    Integer last = indexes.get(leaves.get(leaves.size() - 1));
    if (begin == null || last == null) {
      throw new IllegalStateException("matched node is not in indexed tree");
    }
    return new int[] {begin, last + 1};
  }

  private static String spanKey(int begin, int end) {
    return begin + ":" + end;
  }

  private static int capture(
      int treeIndex,
      String field,
      List<Rule> rules,
      Tree tree,
      IdentityHashMap<Tree, Integer> indexes) {
    Set<String> emitted = new HashSet<>();
    int matchCount = 0;
    int patternIndex = 0;
    for (Rule rule : rules) {
      TregexMatcher matcher = rule.pattern.matcher(tree);
      while (matcher.find()) {
        Tree named = matcher.getNode(field);
        if (named == null) throw new IllegalStateException("pattern did not bind " + field);
        int[] span = originalSpan(named, indexes);
        if (!emitted.add(spanKey(span[0], span[1]))) continue;
        System.out.printf(
            "MATCH\t%d\t%s\t%d\t%d\t%s\t%d\tfalse%n",
            treeIndex, field, span[0], span[1], nodeText(named), patternIndex);
        matchCount++;
      }
      patternIndex++;
    }
    if (matchCount == 0) System.out.printf("MISS\t%d\t%s%n", treeIndex, field);
    return matchCount;
  }

  private static int captureAndPrune(
      int treeIndex,
      String field,
      List<Rule> rules,
      Tree original,
      int[] surgeryCount) {
    Tree working = original.deepCopy();
    IdentityHashMap<Tree, Integer> indexes = new IdentityHashMap<>();
    List<Tree> leaves = working.getLeaves();
    for (int index = 0; index < leaves.size(); index++) indexes.put(leaves.get(index), index);
    Set<String> emitted = new HashSet<>();
    int matchCount = 0;
    boolean progressed = true;
    while (progressed && working != null) {
      progressed = false;
      int patternIndex = 0;
      for (Rule rule : rules) {
        if (rule.operation == null) {
          patternIndex++;
          continue;
        }
        TregexMatcher matcher = rule.pattern.matcher(working);
        if (!matcher.find()) {
          patternIndex++;
          continue;
        }
        Tree named = matcher.getNode(field);
        if (named == null) throw new IllegalStateException("pattern did not bind " + field);
        int[] span = originalSpan(named, indexes);
        if (emitted.add(spanKey(span[0], span[1]))) {
          System.out.printf(
              "MATCH\t%d\t%s\t%d\t%d\t%s\t%d\ttrue%n",
              treeIndex, field, span[0], span[1], nodeText(named), patternIndex);
          matchCount++;
        }
        working = Tsurgeon.processPattern(rule.pattern, rule.operation, working);
        surgeryCount[0]++;
        progressed = true;
        break;
      }
    }
    if (matchCount == 0) System.out.printf("MISS\t%d\t%s%n", treeIndex, field);
    return matchCount;
  }

  private static Tree pruneAll(Tree working, List<Rule> rules, int[] surgeryCount) {
    boolean progressed = true;
    while (progressed && working != null) {
      progressed = false;
      for (Rule rule : rules) {
        if (rule.operation == null) continue;
        TregexMatcher matcher = rule.pattern.matcher(working);
        if (!matcher.find()) continue;
        working = Tsurgeon.processPattern(rule.pattern, rule.operation, working);
        surgeryCount[0]++;
        progressed = true;
        break;
      }
    }
    return working;
  }

  public static void main(String[] args) throws Exception {
    if (args.length != 2) {
      throw new IllegalArgumentException(
          "usage: SunPaperIndependentContextBridge <rule-plan.tsv> <trees.txt>");
    }
    List<Rule> rules = loadRules(Paths.get(args[0]));
    Map<String, List<Rule>> grouped = groupRules(rules);
    List<String> trees = Files.readAllLines(Paths.get(args[1]), StandardCharsets.UTF_8);
    int treeCount = 0;
    int matchCount = 0;
    int surgeryCount = 0;
    int terminalTreeRemovalCount = 0;
    for (String rawTree : trees) {
      if (rawTree.trim().isEmpty()) continue;
      Tree original = Tree.valueOf(rawTree);
      IdentityHashMap<Tree, Integer> originalIndexes = new IdentityHashMap<>();
      List<Tree> originalLeaves = original.getLeaves();
      for (int index = 0; index < originalLeaves.size(); index++) {
        originalIndexes.put(originalLeaves.get(index), index);
      }

      int[] captureSurgeries = new int[] {0};
      for (Map.Entry<String, List<Rule>> entry : grouped.entrySet()) {
        if (entry.getKey().equals("action")) continue;
        boolean destructive = entry.getValue().stream().anyMatch(rule -> rule.operation != null);
        if (destructive) {
          matchCount += captureAndPrune(
              treeCount, entry.getKey(), entry.getValue(), original, captureSurgeries);
        } else {
          matchCount += capture(
              treeCount, entry.getKey(), entry.getValue(), original, originalIndexes);
        }
      }
      surgeryCount += captureSurgeries[0];

      Tree working = original.deepCopy();
      IdentityHashMap<Tree, Integer> workingIndexes = new IdentityHashMap<>();
      List<Tree> workingLeaves = working.getLeaves();
      for (int index = 0; index < workingLeaves.size(); index++) {
        workingIndexes.put(workingLeaves.get(index), index);
      }
      int[] localSurgeries = new int[] {0};
      for (String field : new String[] {"modality", "condition", "constraint", "exception"}) {
        List<Rule> fieldRules = grouped.get(field);
        if (fieldRules != null) working = pruneAll(working, fieldRules, localSurgeries);
        if (working == null) break;
      }
      surgeryCount += localSurgeries[0];
      if (working == null) {
        terminalTreeRemovalCount++;
        System.out.printf("MISS\t%d\taction%n", treeCount);
      } else {
        List<Rule> actionRules = grouped.get("action");
        if (actionRules == null) throw new IllegalStateException("action rules missing");
        matchCount += capture(treeCount, "action", actionRules, working, workingIndexes);
      }
      System.out.printf(
          "FINAL\t%d\t%s%n",
          treeCount,
          working == null
              ? "<TREE_REMOVED>"
              : working.toString().replace('\t', ' ').replace('\n', ' '));
      treeCount++;
    }
    System.out.printf("TERMINAL_TREE_REMOVALS\t%d%n", terminalTreeRemovalCount);
    System.out.printf(
        "SUMMARY\t%d\t%d\t%d\t%d%n",
        treeCount, rules.size(), matchCount, surgeryCount);
  }
}
