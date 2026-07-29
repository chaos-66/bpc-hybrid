import edu.stanford.nlp.trees.Tree;
import edu.stanford.nlp.trees.tregex.TregexMatcher;
import edu.stanford.nlp.trees.tregex.TregexPattern;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.IdentityHashMap;
import java.util.List;

/**
 * Diagnostic-only B3a v2 bridge.
 *
 * Compiles every frozen candidate independently and reports every live
 * constituent match as original token begin/end offsets.  It performs no
 * tree-rewrite operation and is not referenced by a production configuration.
 */
public final class SunPhraseRuleDiagnosticB3aV2 {
  private static final class Rule {
    final int index;
    final String id;
    final TregexPattern pattern;

    Rule(int index, String id, TregexPattern pattern) {
      this.index = index;
      this.id = id;
      this.pattern = pattern;
    }
  }

  private SunPhraseRuleDiagnosticB3aV2() {}

  private static String safe(String value) {
    return value.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ');
  }

  private static List<Rule> loadRules(Path planPath) throws Exception {
    List<Rule> rules = new ArrayList<>();
    int index = 0;
    for (String raw : Files.readAllLines(planPath, StandardCharsets.UTF_8)) {
      if (raw.trim().isEmpty() || raw.startsWith("#")) continue;
      String[] parts = raw.split("\\t", -1);
      if (parts.length != 2 || parts[0].trim().isEmpty() || parts[1].trim().isEmpty()) {
        throw new IllegalArgumentException("invalid diagnostic rule-plan line");
      }
      String id = parts[0];
      if (!id.matches("[A-Za-z0-9_\\-]+")) {
        throw new IllegalArgumentException("unsafe diagnostic pattern id");
      }
      try {
        TregexPattern compiled = TregexPattern.compile(parts[1]);
        rules.add(new Rule(index, id, compiled));
        System.out.printf("COMPILE\t%d\t%s\ttrue\t-%n", index, id);
      } catch (RuntimeException exc) {
        rules.add(new Rule(index, id, null));
        System.out.printf(
            "COMPILE\t%d\t%s\tfalse\t%s%n",
            index,
            id,
            safe(exc.getClass().getSimpleName()));
      }
      index++;
    }
    if (rules.isEmpty()) throw new IllegalArgumentException("diagnostic rule plan is empty");
    return rules;
  }

  private static int[] originalSpan(
      Tree node, IdentityHashMap<Tree, Integer> originalLeafIndexes) {
    int begin = Integer.MAX_VALUE;
    int end = -1;
    for (Tree leaf : node.getLeaves()) {
      Integer leafIndex = originalLeafIndexes.get(leaf);
      if (leafIndex == null) {
        throw new IllegalStateException("matched leaf lacks original token index");
      }
      begin = Math.min(begin, leafIndex);
      end = Math.max(end, leafIndex + 1);
    }
    if (begin == Integer.MAX_VALUE || end <= begin) {
      throw new IllegalStateException("matched constituent has no tokens");
    }
    return new int[] {begin, end};
  }

  public static void main(String[] args) throws Exception {
    if (args.length != 2) {
      throw new IllegalArgumentException(
          "usage: SunPhraseRuleDiagnosticB3aV2 <candidate-plan.tsv> <trees.txt>");
    }
    List<Rule> rules = loadRules(Paths.get(args[0]));
    List<String> trees = Files.readAllLines(Paths.get(args[1]), StandardCharsets.UTF_8);
    int treeCount = 0;
    int compiledCount = 0;
    int matchCount = 0;
    for (Rule rule : rules) if (rule.pattern != null) compiledCount++;

    for (String rawTree : trees) {
      if (rawTree.trim().isEmpty()) continue;
      Tree tree = Tree.valueOf(rawTree);
      if (tree == null) throw new IllegalArgumentException("malformed constituency tree");
      IdentityHashMap<Tree, Integer> leafIndexes = new IdentityHashMap<>();
      List<Tree> leaves = tree.getLeaves();
      for (int leafIndex = 0; leafIndex < leaves.size(); leafIndex++) {
        leafIndexes.put(leaves.get(leafIndex), leafIndex);
      }
      for (Rule rule : rules) {
        if (rule.pattern == null) continue;
        TregexMatcher matcher = rule.pattern.matcher(tree);
        while (matcher.find()) {
          Tree node = matcher.getNode("constraint");
          if (node == null) {
            throw new IllegalStateException(
                "candidate matched without binding constraint: " + rule.id);
          }
          int[] span = originalSpan(node, leafIndexes);
          System.out.printf(
              "MATCH\t%d\t%d\t%s\t%d\t%d%n",
              treeCount, rule.index, rule.id, span[0], span[1]);
          matchCount++;
        }
      }
      treeCount++;
    }
    System.out.printf(
        "SUMMARY\t%d\t%d\t%d\t%d%n",
        treeCount, rules.size(), compiledCount, matchCount);
  }
}
