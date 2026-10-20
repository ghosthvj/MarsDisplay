using System;
using System.Linq;
using System.Reflection;
using System.Threading;

[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

namespace UsbScreenProbe
{
    internal static class Program
    {
        internal const string MarkerVariable = "USB_SCREEN_PROBE_OWNED_CHILD";

        public static int Main(string[] args)
        {
            bool worker = args.Length >= 2 && args[0] == "--owned-worker" &&
                args[1].Length == 32 && args[1] == Environment.GetEnvironmentVariable(MarkerVariable);
            Environment.SetEnvironmentVariable(MarkerVariable, null);
            if (worker)
            {
                string marker = args[1];
                args = args.Skip(2).ToArray();
                // Internal mode shares every public validation and confirmation step.
                try
                {
                    // If the parent dies before assigning the job, leave without touching inventory/USB.
                    using (var gate = EventWaitHandle.OpenExisting("Local\\UsbScreenProbe-" + marker))
                        if (!gate.WaitOne(5000)) throw new TimeoutException();
                    return Probe.Run(args, Console.In, Console.Out, Console.Error,
                        Probe.Inventory, delegate { return new NativePort(); }, new Clock(), Probe.LoadPattern());
                }
                catch
                {
                    Console.Error.WriteLine("E7: Probe could not complete. Check the screen before another explicit run.");
                    return 7;
                }
            }
            if (!Probe.ValidArgs(args))
            {
                Console.Error.WriteLine(Probe.ArgumentError);
                Console.Error.Write(Probe.Help);
                return 2;
            }
            int result;
            try
            {
                string marker = Guid.NewGuid().ToString("N");
                // Only allowlisted words and numeric COM names reach the argument string; no shell.
                string arguments = "--owned-worker " + marker + (args.Length == 0 ? "" : " " + String.Join(" ", args));
                using (var child = OwnedChild.Start(Assembly.GetExecutingAssembly().Location, arguments, marker))
                    result = Supervisor.Wait(child, 90000, Console.Error);
            }
            catch
            {
                Console.Error.WriteLine("E7: Could not start the isolated probe worker. Obtain a verified build.");
                result = 7;
            }
            if (args.Length == 0 && !Console.IsInputRedirected)
            {
                Console.WriteLine("Press Enter to close.");
                Console.ReadLine();
            }
            return result;
        }
    }
}
