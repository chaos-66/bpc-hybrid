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
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Enhanced development bridge: multi non-overlapping matches per field. */
public final class SunPhraseRuleBatchBridgeMulti {
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
  private SunPhraseRuleBatchBridgeMulti() {}
  private static List<Rule> loadRules(Path planPath) throws Exception {
    List<Rule> rules = new ArrayList<>();
    for (String raw : Files.readAllLines(planPath, StandardCharsets.UTF_8)) {
      if (raw.trim().isEmpty() || raw.startsWith("#")) continue;
      String[] parts = raw.split("\t", -1);
      if (parts.length != 3 || parts[0].trim().isEmpty() || parts[1].trim().isEmpty()) {
        throw new IllegalArgumentException("invalid rule-plan line: " + raw);
      }
      rules.add(new Rule(parts[0], TregexPattern.compile(parts[1]),
          parts[2].trim().isEmpty() ? null : Tsurgeon.parseOperation(parts[2])));
    }
    if (rules.isEmpty()) throw new IllegalArgumentException("rule plan is empty");
    return rules;
  }
  private static Map<String, List<Rule>> groupRules(List<Rule> rules) {
    Map<String, List<Rule>> grouped = new LinkedHashMap<>();
    for (Rule rule : rules) grouped.computeIfAbsent(rule.field, ignored -> new ArrayList<>()).add(rule);
    return grouped;
  }
  private static String nodeText(Tree node) {
    List<String> words = new ArrayList<>();
    for (Tree leaf : node.getLeaves()) words.add(leaf.label().value());
    return String.join(" ", words).replace('\t', ' ').replace('\n', ' ');
  }
  private static int[] originalSpan(Tree node, IdentityHashMap<Tree, Integer> originalLeafIndexes) {
    int begin = Integer.MAX_VALUE; int end = -1;
    for (Tree leaf : node.getLeaves()) {
      Integer index = originalLeafIndexes.get(leaf);
      if (index == null) throw new IllegalStateException("matched leaf lost its original index");
      begin = Math.min(begin, index); end = Math.max(end, index + 1);
    }
    if (end < 0) throw new IllegalStateException("matched node has no leaves");
    return new int[] {begin, end};
  }
  private static boolean overlaps(int begin, int end, List<int[]> taken) {
    for (int[] span : taken) if (begin < span[1] && end > span[0]) return true;
    return false;
  }
  public static void main(String[] args) throws Exception {
    if (args.length != 2) throw new IllegalArgumentException(
        "usage: SunPhraseRuleBatchBridgeMulti <rule-plan.tsv> <trees.txt>");
    List<Rule> rules = loadRules(Paths.get(args[0]));
    Map<String, List<Rule>> grouped = groupRules(rules);
    List<String> trees = Files.readAllLines(Paths.get(args[1]), StandardCharsets.UTF_8);
    int treeCount = 0, matchCount = 0, surgeryCount = 0, terminalTreeRemovalCount = 0;
    for (String rawTree : trees) {
      if (rawTree.trim().isEmpty()) continue;
      Tree working = Tree.valueOf(rawTree);
      IdentityHashMap<Tree, Integer> leafIndexes = new IdentityHashMap<>();
      List<Tree> originalLeaves = working.getLeaves();
      for (int index = 0; index < originalLeaves.size(); index++) leafIndexes.put(originalLeaves.get(index), index);
      for (Map.Entry<String, List<Rule>> fieldRules : grouped.entrySet()) {
        String field = fieldRules.getKey();
        if (working == null) { System.out.printf("MISS\t%d\t%s%n", treeCount, field); continue; }
        List<int[]> taken = new ArrayList<>();
        boolean anyMatch = false; boolean progressed = true;
        while (progressed && working != null) {
          progressed = false; int patternIndex = 0;
          for (Rule rule : fieldRules.getValue()) {
            TregexMatcher matcher = rule.pattern.matcher(working);
            Tree named = null; int[] span = null;
            while (matcher.find()) {
              Tree candidate = matcher.getNode(field);
              if (candidate == null) throw new IllegalStateException("pattern matched but did not bind node name " + field);
              int[] candidateSpan = originalSpan(candidate, leafIndexes);
              if (overlaps(candidateSpan[0], candidateSpan[1], taken)) continue;
              named = candidate; span = candidateSpan; break;
            }
            if (named == null) { patternIndex++; continue; }
            boolean operated = rule.operation != null;
            if (operated) {
              // B0-R1-BRIDGE (2026-08-04): Tsurgeon.processPattern applies
              // the operation to EVERY node matching the pattern, while this
              // loop records only the first non-overlapping candidate.
              // Recording one match while consuming several would silently
              // drop spans from the output contract, so an operated rule is
              // required to match exactly one node; otherwise fail closed.
              int extraMatches = 0;
              while (matcher.find()) extraMatches++;
              if (extraMatches > 0) {
                throw new IllegalStateException(
                    "operated Tregex rule matched " + (extraMatches + 1)
                        + " nodes in tree " + treeCount + " field " + field
                        + "; one match would be recorded but Tsurgeon would consume all");
              }
            }
            System.out.printf("MATCH\t%d\t%s\t%d\t%d\t%s\t%d\t%s%n", treeCount, field, span[0], span[1], nodeText(named), patternIndex, operated ? "true" : "false");
            matchCount++; anyMatch = true; taken.add(span); progressed = true;
            if (operated) {
              working = Tsurgeon.processPattern(rule.pattern, rule.operation, working);
              surgeryCount++;
              if (working == null) terminalTreeRemovalCount++;
            }
            break;
          }
        }
        if (!anyMatch) System.out.printf("MISS\t%d\t%s%n", treeCount, field);
      }
      System.out.printf("FINAL\t%d\t%s%n", treeCount, working == null ? "<TREE_REMOVED>" : working.toString().replace('\t', ' ').replace('\n', ' '));
      treeCount++;
    }
    System.out.printf("TERMINAL_TREE_REMOVALS\t%d%n", terminalTreeRemovalCount);
    System.out.printf("SUMMARY\t%d\t%d\t%d\t%d%n", treeCount, rules.size(), matchCount, surgeryCount);
  }
}
