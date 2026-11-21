// In-app documentation. Country-neutral: it describes the tool, not one run.

import { Bundle } from "../bundle/types";

export default function Guide({ bundle }: { bundle: Bundle | null }) {
  const country = bundle?.source.country;
  return (
    <div className="stack guide">
      <section className="card">
        <h3>What this site shows</h3>
        <p>
          FABLE Explorer reads the results of a FABLE Calculator workbook. Each pathway
          (scenario) in the workbook is recalculated, and the output tables of all
          pathways are packed into one file, <code>bundle.json</code>. This site renders
          that file in the browser. Nothing is uploaded to a server.
        </p>
        <p>
          The site works with any country's FABLE workbook.
          {country ? <> The bundle open now is for <strong>{country}</strong>.</> : null}
        </p>
      </section>

      <section className="card">
        <h3>Loading results</h3>
        <ul>
          <li>The site opens with the bundle published alongside it.</li>
          <li>
            To look at another run, drag its <code>bundle.json</code> onto the page, or use{" "}
            <strong>Open bundle</strong> at the top right. The file stays on your computer.
          </li>
          <li>
            Bundles from older versions of the tool still open. Summary, Compare pathways and
            IAMC data need a bundle built with schema 1.1.0 or later.
          </li>
          <li>
            Runs with more than seven pathways open in ensemble view. Grey shows every pathway; you
            choose up to seven to colour, by name or with the quick picks (lowest emissions, most
            food and so on). Design runs also show which lever settings move each indicator.
          </li>
          <li>
            Pathway colours follow the IPCC AR6 scenario palette and stay fixed per pathway on
            every chart. Each chart also has a legend or labels, so colour is never the only cue.
          </li>
        </ul>
      </section>

      <section className="card">
        <h3>Tabs</h3>
        <dl className="kv">
          <dt>Summary</dt>
          <dd>
            Where every pathway lands on the headline indicators in a chosen year, a few plain
            the main findings in plain sentences, and a scorecard of the numbers. Needs the IAMC table.
          </dd>
          <dt>Compare pathways</dt>
          <dd>
            Any IAMC variable: pathways ranked in one year, the trajectory over time, what a total
            is made of (for example land cover by type), and two pathways side by side.
          </dd>
          <dt>IAMC data</dt>
          <dd>The IAMC table itself, with charts, the variable mapping and CSV downloads.</dd>
          <dt>Workbook tables</dt>
          <dd>
            Any raw output table of the workbook for the chosen pathways, as values or as the
            difference from the baseline. Tables with a product or group dimension show a selector.
          </dd>
          <dt>Deviation ranking</dt>
          <dd>Every workbook metric ranked by how far pathways move away from the baseline.</dd>
          <dt>Run details</dt>
          <dd>Workbook, run, pathways, baseline and the list of output tables.</dd>
        </dl>
      </section>

      <section className="card">
        <h3>IAMC export</h3>
        <p>
          The IAMC format is the shared layout of integrated assessment modelling: one row
          per model, scenario, region and variable, one column per year. Variable names and
          units follow{" "}
          <a href="https://github.com/IAMconsortium/common-definitions" target="_blank" rel="noreferrer">
            IAMconsortium/common-definitions
          </a>
          , so FABLE results can be compared with other models or uploaded to a scenario
          explorer.
        </p>
        <table className="grid compact doc">
          <thead>
            <tr><th>Column</th><th>Content</th></tr>
          </thead>
          <tbody>
            <tr><td>Model</td><td>Name chosen when the bundle was built, for example <code>FABLE-Pakistan v1</code>. Defaults to <code>FABLE-&lt;country&gt;</code>.</td></tr>
            <tr><td>Scenario</td><td>FABLE pathway name (can be renamed in <code>config.yaml</code>).</td></tr>
            <tr><td>Region</td><td>Country name as written in common-definitions.</td></tr>
          </tbody>
        </table>
        <h4>What is covered</h4>
        <ul>
          <li>Land cover: cropland, pasture, forest, built-up and other natural land; forest area change.</li>
          <li>Agricultural production, net trade and demand, by crop type and livestock product, in million t dry matter.</li>
          <li>Crop yields per harvested hectare.</li>
          <li>Food availability in kcal per person per day.</li>
          <li>AFOLU emissions of CH4, N2O and CO2, gross CO2 emissions and removals, and Kyoto gases.</li>
          <li>Nitrogen fertiliser use, irrigation water, agricultural employment and price indices.</li>
        </ul>
        <h4>Conversions to know about</h4>
        <ul>
          <li>
            FABLE reports fresh weight. IAMC asks for dry matter, so each product is
            multiplied by a dry-matter share from <code>fable/iamc/products.csv</code>.
          </li>
          <li>
            Oils, cakes and raw sugar count in trade only, under their parent crop type, so
            production is not counted twice. Demand is production minus net exports.
          </li>
          <li>
            Kyoto gases are summed with the GWP-100 basis shown on the IAMC tab (AR4 by
            default, as common-definitions recommends). FABLE's own CO2e uses AR6.
          </li>
          <li>
            The “How each variable is computed” table on the IAMC tab lists the source
            column and conversion for every variable.
          </li>
        </ul>
      </section>

      <section className="card">
        <h3>Building a bundle</h3>
        <p>On a computer with Python and the repository installed:</p>
        <pre className="cmd">{`# recalculate every pathway (needs Excel) and build bundle.json + IAMC files
python -m fable.compute run workbooks/<COUNTRY>.xlsx --model "FABLE-<Country> v1"

# or from an existing run directory, no Excel needed
python -m fable.compute bundle exports/<run_dir> --model "FABLE-<Country> v1"

# open this site locally with the new bundle
python -m fable.compute view`}</pre>
        <p className="muted">
          The bundle goes to <code>viewer/public/data/bundle.json</code>. The IAMC files go
          to <code>&lt;run_dir&gt;/iamc/</code>: a CSV, an Excel workbook (about, data,
          meta and mapping sheets) and the mapping table. The desktop launcher
          (<code>Launch_Launcher</code>) does the same with buttons.
        </p>
      </section>
    </div>
  );
}
